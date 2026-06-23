"""
rag_mcp.py
RAG (Retrieval-Augmented Generation) — Model Context Protocol.
Parses uploaded CSV/datasheet files, extracts structured summaries,
and injects them as context into the OpenRouter API request payload.
"""

import csv
import io
import logging
import math
import random
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Dtype inference thresholds — named constants
# ──────────────────────────────────────────────
_NUMERIC_DOMINANCE_THRESHOLD = 0.80
_DATE_DOMINANCE_THRESHOLD = 0.80
_CATEGORICAL_UNIQUE_RATIO = 0.50
_CATEGORICAL_MIN_ROWS = 5
_TEXT_AVG_LENGTH_THRESHOLD = 50
_CATEGORICAL_MAX_UNIQUE = 20

# Context injection limits
_MAX_SNIPPET_CHARS = 3000
_MAX_SNIPPET_LINES = 30


@dataclass
class ColumnProfile:
    """Statistical profile of a single datasheet column."""
    name: str
    dtype: str  # 'numeric', 'categorical', 'text', 'date', 'mixed'
    non_null_count: int
    null_count: int
    unique_count: int
    sample_values: List[str]
    # Numeric stats (only if dtype == 'numeric')
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    # Categorical stats (only if dtype == 'categorical')
    top_values: List[Tuple[str, int]] = field(default_factory=list)
    # Text stats
    avg_length: Optional[float] = None


@dataclass
class RagContext:
    """
    Structured context extracted from an uploaded datasheet.
    This gets serialised and injected into the OpenRouter system prompt.
    """
    filename: str
    row_count: int
    column_count: int
    columns: List[ColumnProfile]
    summary_stats: Dict[str, Any] = field(default_factory=dict)
    raw_text_snippet: str = ""
    detected_issues: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────

def _filter_non_null(values: List[str]) -> List[str]:
    """Remove empty or whitespace-only strings from a column's values."""
    return [v for v in values if v and v.strip()]


def _infer_dtype(non_null_values: List[str]) -> str:
    """
    Infer the data type of a column from pre-filtered (non-null) values.
    Caller must pass already-filtered values.
    """
    if not non_null_values:
        return "text"

    total = len(non_null_values)
    numeric_count = 0
    date_count = 0

    for v in non_null_values:
        v_stripped = (
            v.strip()
            .replace(",", "")
            .replace("$", "")
            .replace("%", "")
            .replace("€", "")
            .replace("£", "")
        )
        try:
            float(v_stripped)
            numeric_count += 1
            continue
        except ValueError:
            pass
        if re.match(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", v):
            date_count += 1

    if numeric_count / total >= _NUMERIC_DOMINANCE_THRESHOLD:
        return "numeric"
    if date_count / total >= _DATE_DOMINANCE_THRESHOLD:
        return "date"

    unique = {v.strip().lower() for v in non_null_values}
    unique_ratio = len(unique) / total

    if unique_ratio < _CATEGORICAL_UNIQUE_RATIO and total > _CATEGORICAL_MIN_ROWS:
        return "categorical"

    avg_len = sum(len(v) for v in non_null_values) / total
    if avg_len > _TEXT_AVG_LENGTH_THRESHOLD:
        return "text"

    if len(unique) <= _CATEGORICAL_MAX_UNIQUE:
        return "categorical"

    return "text"


def _top_categorical_values(
    non_null: List[str],
    n: int = 10,
) -> List[Tuple[str, int]]:
    """
    Count categorical values case-insensitively.
    Returns the most common (display_value, count) pairs.
    """
    groups: Dict[str, Counter] = {}
    for v in non_null:
        key = v.strip().lower()
        if key not in groups:
            groups[key] = Counter()
        groups[key][v.strip()] += 1

    result: List[Tuple[str, int]] = []
    for originals in groups.values():
        display = originals.most_common(1)[0][0]
        total_count = sum(originals.values())
        result.append((display, total_count))

    result.sort(key=lambda x: x[1], reverse=True)
    return result[:n]


def _profile_column(name: str, raw_values: List[str]) -> ColumnProfile:
    """Build a statistical profile of a single column."""
    non_null = _filter_non_null(raw_values)
    null_count = len(raw_values) - len(non_null)
    unique_set = {v.strip().lower() for v in non_null}

    dtype = _infer_dtype(non_null)
    # FIXED: random sample instead of first 5
    sample = random.sample(non_null, min(5, len(non_null))) if non_null else []

    profile = ColumnProfile(
        name=name,
        dtype=dtype,
        non_null_count=len(non_null),
        null_count=null_count,
        unique_count=len(unique_set),
        sample_values=sample,
    )

    if dtype == "numeric":
        nums: List[float] = []
        for v in non_null:
            try:
                nums.append(
                    float(
                        v.strip()
                        .replace(",", "")
                        .replace("$", "")
                        .replace("%", "")
                        .replace("€", "")
                        .replace("£", "")
                    )
                )
            except ValueError:
                pass
        if nums:
            nums.sort()
            n = len(nums)
            profile.min_val = nums[0]
            profile.max_val = nums[-1]
            profile.mean = sum(nums) / n
            # Sample std dev (Bessel's correction — divide by N-1)
            profile.std = (
                math.sqrt(sum((x - profile.mean) ** 2 for x in nums) / (n - 1))
                if n > 1
                else 0.0
            )
            # Median
            mid = n // 2
            profile.median = nums[mid] if n % 2 else (nums[mid - 1] + nums[mid]) / 2

    elif dtype == "categorical":
        profile.top_values = _top_categorical_values(non_null)

    elif dtype == "text":
        profile.avg_length = (
            sum(len(v) for v in non_null) / len(non_null) if non_null else 0.0
        )

    return profile


def _truncate_snippet(snippet: str) -> str:
    """Truncate raw snippet to stay within LLM context limits."""
    lines = snippet.splitlines()[:_MAX_SNIPPET_LINES]
    truncated = "\n".join(lines)
    if len(truncated) > _MAX_SNIPPET_CHARS:
        truncated = truncated[:_MAX_SNIPPET_CHARS]
        truncated += f"\n... [truncated at {_MAX_SNIPPET_CHARS} chars]"
    return truncated


# ──────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────

def parse_csv_datasheet(
    content: str,
    filename: str = "uploaded.csv",
    sample_rows: int = 200,
) -> Optional[RagContext]:
    """
    Parse a CSV datasheet and extract structured RAG context.

    Parameters
    ----------
    content : str
        Raw CSV content as a string.
    filename : str
        Original filename for reference.
    sample_rows : int
        Maximum number of rows to analyse (for performance on large files).

    Returns
    -------
    Optional[RagContext]
        Structured context, or None if parsing fails.
    """
    try:
        # Detect delimiter
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(content[:4096])
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","

        # Use raw csv.reader for index-based access (handles duplicate column names)
        raw_reader = csv.reader(io.StringIO(content), delimiter=delimiter)
        headers_raw = next(raw_reader, None)
        if not headers_raw:
            return None

        # Count total rows efficiently
        total_rows_in_file = 0
        all_rows_raw: List[List[str]] = []
        for row in raw_reader:
            total_rows_in_file += 1
            if len(all_rows_raw) < sample_rows:
                all_rows_raw.append(row)
            # FIXED: Stop reading entire file if we have enough samples
            # and we already passed sample_rows (just counting now)
            # We keep counting total but don't store more rows

        if not all_rows_raw:
            return None

        # Build column profiles — index-based to handle duplicates correctly
        col_indices: Dict[str, List[int]] = {}
        for idx, h in enumerate(headers_raw):
            col_indices.setdefault(h, []).append(idx)

        columns: List[ColumnProfile] = []
        seen_names: Set[str] = set()

        # FIXED: Duplicate column handling with proper conflict detection
        # Build a set of ALL original column names first
        all_original_names = set(headers_raw)

        for original_name, indices in col_indices.items():
            for occurrence, col_idx in enumerate(indices):
                if occurrence == 0:
                    display_name = original_name
                else:
                    # Try occurrence-based name first
                    display_name = f"{original_name}_{occurrence}"
                    # Ensure no clash with any existing original column name
                    dedup_counter = occurrence
                    while (
                        display_name in seen_names
                        or display_name in all_original_names
                    ):
                        dedup_counter += 1
                        display_name = f"{original_name}_{dedup_counter}"
                seen_names.add(display_name)

                col_values = [
                    row[col_idx] if col_idx < len(row) else ""
                    for row in all_rows_raw
                ]
                columns.append(_profile_column(display_name, col_values))

        # Build summary stats
        numeric_cols = [c for c in columns if c.dtype == "numeric"]
        categorical_cols = [c for c in columns if c.dtype == "categorical"]

        summary_stats = {
            "total_rows": total_rows_in_file,
            "rows_sampled": len(all_rows_raw),
            "numeric_columns": len(numeric_cols),
            "categorical_columns": len(categorical_cols),
            "text_columns": len([c for c in columns if c.dtype == "text"]),
            "date_columns": len([c for c in columns if c.dtype == "date"]),
            "null_percentage": round(
                sum(c.null_count for c in columns)
                / max(sum(c.non_null_count + c.null_count for c in columns), 1)
                * 100,
                1,
            ),
        }

        # Detect issues
        issues: List[str] = []
        for c in columns:
            if c.null_count > 0:
                pct = c.null_count / max(c.non_null_count + c.null_count, 1) * 100
                issues.append(
                    f"Column '{c.name}' has {c.null_count} missing values ({pct:.1f}%)."
                )
        if summary_stats["null_percentage"] > 20:
            issues.append(
                f"High null rate: {summary_stats['null_percentage']}% of cells are empty."
            )

        # Build raw text snippet (first 30 rows)
        header_str = ",".join(headers_raw)
        row_lines = [
            ",".join(str(row[i]) if i < len(row) else "" for i in range(len(headers_raw)))
            for row in all_rows_raw[:30]
        ]
        raw_text_snippet = f"{header_str}\n" + "\n".join(row_lines)

        return RagContext(
            filename=filename,
            row_count=total_rows_in_file,
            column_count=len(columns),
            columns=columns,
            summary_stats=summary_stats,
            raw_text_snippet=raw_text_snippet,
            detected_issues=issues,
        )

    except Exception as exc:
        logger.error("CSV parse failed for %s: %s", filename, exc, exc_info=True)
        return None


def extract_structured_context(rag_ctx: RagContext) -> str:
    """
    Convert a RagContext into a structured text block for injection
    into the OpenRouter / GPT-4.1-nano system prompt as RAG context.
    """
    parts = [
        f"[DATASHEET CONTEXT — File: {rag_ctx.filename}]",
        f"Total rows: {rag_ctx.row_count} | Rows sampled: {rag_ctx.summary_stats.get('rows_sampled', rag_ctx.row_count)} | Columns: {rag_ctx.column_count}",
        f"Null rate: {rag_ctx.summary_stats.get('null_percentage', '?')}%",
        "",
        "Column Profiles:",
    ]

    for col in rag_ctx.columns:
        line = (
            f"  - {col.name} ({col.dtype}): "
            f"{col.non_null_count} values, {col.unique_count} unique"
        )
        if col.dtype == "numeric" and col.min_val is not None:
            line += (
                f" | range: {col.min_val:.2f} to {col.max_val:.2f}"
                f", mean: {col.mean:.2f}, median: {col.median:.2f}"
            )
            if col.std and col.std > 0:
                line += f", std: {col.std:.2f}"
        elif col.dtype == "categorical" and col.top_values:
            top_str = ", ".join(f"{v[0]}({v[1]})" for v in col.top_values[:5])
            line += f" | top: {top_str}"
        parts.append(line)

    if rag_ctx.detected_issues:
        parts.append("")
        parts.append("Data Quality Issues:")
        for issue in rag_ctx.detected_issues:
            parts.append(f"  ! {issue}")

    # Append truncated raw sample
    parts.append("")
    parts.append("Raw Sample (first 30 rows):")
    parts.append(_truncate_snippet(rag_ctx.raw_text_snippet))
    parts.append("[/DATASHEET CONTEXT]")

    return "\n".join(parts)