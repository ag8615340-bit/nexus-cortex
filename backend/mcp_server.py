"""
mcp_server.py — Model Context Protocol (MCP) Server
Kaggle "MCP Server" concept requirement.
Exposes CSV analysis tools via MCP protocol for agent consumption.
Follows the Model Context Protocol pattern: Tool definitions → Handler → Transport.
"""

import csv
import io
from typing import Any, Dict, List, Optional
from collections import Counter


class MCPTool:
    """A single MCP tool definition with name, description, params schema, and handler."""
    def __init__(self, name: str, description: str, handler, params: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.handler = handler
        self.params = params or {}


class MCPServer:
    """
    Lightweight MCP Server following Model Context Protocol.

    Features:
    - Tool discovery (list_tools)
    - Tool execution (call_tool)
    - Dynamic tool registration (register_tool)
    - Built-in CSV analysis tools
    """

    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register built-in CSV analysis tools."""
        self.register_tool(MCPTool(
            name="csv_summarize",
            description="Summarize a CSV: row count, columns, nulls, dtypes",
            handler=self._handle_csv_summarize,
            params={"csv_content": {"type": "string", "description": "Raw CSV text"}},
        ))
        self.register_tool(MCPTool(
            name="csv_column_stats",
            description="Get statistics for a specific column (mean, min, max, unique values)",
            handler=self._handle_csv_column_stats,
            params={
                "csv_content": {"type": "string", "description": "Raw CSV text"},
                "column_name": {"type": "string", "description": "Column to analyze"},
            },
        ))
        self.register_tool(MCPTool(
            name="csv_filter",
            description="Filter CSV rows by column value match",
            handler=self._handle_csv_filter,
            params={
                "csv_content": {"type": "string", "description": "Raw CSV text"},
                "column": {"type": "string", "description": "Column name to filter on"},
                "value": {"type": "string", "description": "Value to match"},
            },
        ))
        self.register_tool(MCPTool(
            name="csv_top_values",
            description="Get top N most common values in a column",
            handler=self._handle_csv_top_values,
            params={
                "csv_content": {"type": "string", "description": "Raw CSV text"},
                "column": {"type": "string", "description": "Column name"},
                "n": {"type": "number", "description": "Number of top values (default: 5)"},
            },
        ))

    def register_tool(self, tool: MCPTool) -> None:
        """Register a new tool (MCP discovery pattern)."""
        self.tools[tool.name] = tool

    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools (MCP discovery endpoint)."""
        return [
            {"name": t.name, "description": t.description, "params": t.params}
            for t in self.tools.values()
        ]

    def call_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool by name with parameters."""
        if name not in self.tools:
            return {"error": f"Tool '{name}' not found. Available: {list(self.tools.keys())}"}
        try:
            result = self.tools[name].handler(**kwargs)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}

    # ── CSV Helpers ──────────────────────────

    def _parse_csv(self, content: str):
        """Parse CSV content into headers and rows."""
        reader = csv.reader(io.StringIO(content))
        headers = next(reader, [])
        rows = list(reader)
        return headers, rows

    # ── Tool Handlers ────────────────────────

    def _handle_csv_summarize(self, csv_content: str = "") -> Dict[str, Any]:
        """Summarize CSV structure and null counts."""
        headers, rows = self._parse_csv(csv_content)
        null_counts = {}
        for i, h in enumerate(headers):
            null_counts[h] = sum(1 for row in rows if i >= len(row) or not row[i].strip())
        return {
            "columns": len(headers),
            "column_names": headers,
            "rows": len(rows),
            "null_counts": null_counts,
            "sample": rows[:5],
        }

    def _handle_csv_column_stats(self, csv_content: str = "", column_name: str = "") -> Dict[str, Any]:
        """Get numeric and categorical stats for one column."""
        headers, rows = self._parse_csv(csv_content)
        if column_name not in headers:
            return {"error": f"Column '{column_name}' not found. Available: {headers}"}
        col_idx = headers.index(column_name)
        values = [row[col_idx].strip() for row in rows if col_idx < len(row) and row[col_idx].strip()]
        unique = list(set(v.lower() for v in values))
        nums = []
        for v in values:
            try:
                nums.append(float(v.replace("$", "").replace(",", "").replace("%", "")))
            except ValueError:
                pass
        stats: Dict[str, Any] = {
            "total_values": len(values),
            "unique_values": len(unique),
            "non_numeric": len(values) - len(nums),
        }
        if nums:
            stats.update({
                "min": round(min(nums), 2),
                "max": round(max(nums), 2),
                "mean": round(sum(nums) / len(nums), 2),
                "median": round(sorted(nums)[len(nums) // 2], 2),
            })
        return stats

    def _handle_csv_filter(self, csv_content: str = "", column: str = "", value: str = "") -> Dict[str, Any]:
        """Filter rows where column matches value (case-insensitive)."""
        headers, rows = self._parse_csv(csv_content)
        if column not in headers:
            return {"error": f"Column '{column}' not found. Available: {headers}"}
        col_idx = headers.index(column)
        filtered = [row for row in rows if col_idx < len(row) and row[col_idx].strip().lower() == value.lower()]
        return {"filtered_rows": len(filtered), "data": filtered[:10], "total_rows": len(rows)}

    def _handle_csv_top_values(self, csv_content: str = "", column: str = "", n: int = 5) -> Dict[str, Any]:
        """Return top N most frequent values in a column."""
        headers, rows = self._parse_csv(csv_content)
        if column not in headers:
            return {"error": f"Column '{column}' not found. Available: {headers}"}
        col_idx = headers.index(column)
        counter: Counter = Counter()
        for row in rows:
            if col_idx < len(row) and row[col_idx].strip():
                counter[row[col_idx].strip()] += 1
        return {"top_values": counter.most_common(min(n, len(counter)))}


# ── Singleton ─────────────────────────────────
_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get or create MCP server singleton."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server