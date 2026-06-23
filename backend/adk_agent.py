"""
adk_agent.py — Google ADK-style Agent using Gemini API
Kaggle "Agent / Multi-agent system (ADK)" concept requirement.
Vibe-coded to work alongside OpenRouter agents.
"""

import os
from typing import Optional, Callable, Dict   # ✅ FIX: ye line add karo
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini with Google API key
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
genai.configure(api_key=GOOGLE_API_KEY)
MODEL = "gemini-2.0-flash"


class GoogleAdkAgent:
    """
    ADK-style agent powered by Google Gemini.
    Provides business analysis just like the OpenRouter agents.
    This is a vibe-coded ADK implementation — follows Google ADK patterns
    (tool registration, system prompts, structured output) without
    requiring the full google-adk package.
    """

    def __init__(self):
        self.model = genai.GenerativeModel(MODEL)
        self.system_prompt = (
            "You are a Google ADK-powered business analyst agent. "
            "You are part of the Nexus Cortex multi-agent ecosystem. "
            "Analyze the given data and provide market, financial, and operational insights. "
            "Be concise (2-4 sentences per point), data-driven, and actionable. "
            "Use **bold** for key metrics. Structure your response with clear sections."
        )
        self.tools: Dict[str, Callable] = {}  # ✅ FIX: proper type annotation

    def register_tool(self, name: str, handler: Callable) -> None:  # ✅ FIX: type hints added
        """Register a tool (ADK pattern)."""
        self.tools[name] = handler

    async def analyze(self, query: str, context: str = "") -> str:
        """Run analysis using Gemini (core ADK agent behavior)."""
        prompt = f"{self.system_prompt}\n\n"
        if context:
            prompt += f"Context:\n{context}\n\n"
        prompt += f"Query:\n{query}"

        if not GOOGLE_API_KEY:
            return "[ADK Agent]: GOOGLE_API_KEY not set in .env file."

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"[ADK Agent Error]: {str(e)}"

    async def analyze_with_tools(self, query: str, context: str = "") -> str:
        """ADK-style analysis with tool usage."""
        result = await self.analyze(query, context)
        # Check if any tools should be invoked based on response
        if self.tools and "csv" in query.lower():
            for name, handler in self.tools.items():
                tool_result = handler(query)
                result += f"\n\n🔧 Tool '{name}' invoked:\n{tool_result}"
        return result


# ── Singleton ─────────────────────────────────
_adk_agent: Optional[GoogleAdkAgent] = None  # ✅ ab Optional kaam karega


def get_adk_agent() -> GoogleAdkAgent:
    """Get or create ADK agent singleton."""
    global _adk_agent
    if _adk_agent is None:
        _adk_agent = GoogleAdkAgent()
    return _adk_agent