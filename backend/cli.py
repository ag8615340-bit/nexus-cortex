#!/usr/bin/env python3
"""
cli.py — Nexus Cortex Agent CLI
Kaggle "Agent Skills (Agents CLI)" concept requirement.
Run agents and MCP tools directly from command line.
"""

import argparse
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(
        description="Nexus Cortex — Agent CLI (Kaggle Agent Skills)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py "analyze sales trends"
  python cli.py "show revenue data" --file data.csv
  python cli.py "market analysis" --agent market
  python cli.py --mcp-list
  python cli.py --mcp-tool csv_summarize --mcp-params '{"csv_content":"a,b\\n1,2"}'
        """,
    )
    parser.add_argument("query", type=str, nargs="?", default="", help="Your business analysis query")
    parser.add_argument("--agent", "-a", choices=["market", "financial", "ops", "all"], default="all",
                        help="Which agent to query (default: all)")
    parser.add_argument("--file", "-f", type=str, help="CSV file path for context")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--mcp-tool", "-m", type=str, help="Call an MCP tool directly (use with --mcp-params)")
    parser.add_argument("--mcp-params", type=str, default="{}", help="JSON params for MCP tool")
    parser.add_argument("--mcp-list", action="store_true", help="List available MCP tools")
    parser.add_argument("--adk", action="store_true", help="Use Google ADK agent instead of default")

    args = parser.parse_args()

    # ── MCP Mode ─────────────────────────────
    if args.mcp_list:
        from mcp_server import get_mcp_server
        mcp = get_mcp_server()
        tools = mcp.list_tools()
        if args.json:
            print(json.dumps(tools, indent=2))
        else:
            print("📦 Available MCP Tools:")
            print("─" * 50)
            for t in tools:
                print(f"  • {t['name']}")
                print(f"    {t['description']}")
                print()
        return

    if args.mcp_tool:
        from mcp_server import get_mcp_server
        mcp = get_mcp_server()
        try:
            params = json.loads(args.mcp_params)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid --mcp-params JSON: {e}")
            sys.exit(1)
        result = mcp.call_tool(args.mcp_tool, **params)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"🔧 MCP Tool: {args.mcp_tool}")
            print("─" * 50)
            print(json.dumps(result, indent=2))
        return

    # ── ADK Agent Mode ───────────────────────
    if args.adk:
        from adk_agent import get_adk_agent
        agent = get_adk_agent()
        context = ""
        if args.file:
            try:
                with open(args.file, "r") as f:
                    context = f.read()
                print(f"📄 Loaded file: {args.file} ({len(context)} chars)")
            except FileNotFoundError:
                print(f"❌ File not found: {args.file}")
                sys.exit(1)
        print("🧠 Running Google ADK Agent...\n")
        import asyncio
        result = asyncio.run(agent.analyze(args.query, context))
        if args.json:
            print(json.dumps({"agent": "adk", "response": result}, indent=2))
        else:
            print(result)
        return

    # ── Default Mode ─────────────────────────
    if not args.query:
        parser.print_help()
        return

    if args.agent == "all":
        agents = ["market_strategist", "financial_analyst", "operations_optimizer"]
    else:
        agent_map = {"market": ["market_strategist"], "financial": ["financial_analyst"], "ops": ["operations_optimizer"]}
        agents = agent_map.get(args.agent, ["market_strategist"])

    context = ""
    if args.file:
        try:
            with open(args.file, "r") as f:
                context = f.read()
        except FileNotFoundError:
            print(f"❌ File not found: {args.file}")
            sys.exit(1)

    if not args.json:
        print(f"🧠 Running {len(agents)} agent(s) for query: {args.query}")
        print("─" * 50)

    results = {}
    for agent in agents:
        display = agent.replace("_", " ").title()
        if args.json:
            results[agent] = {"status": "processed", "query": args.query, "context_size": len(context)}
        else:
            print(f"\n🤖 {display}")
            print(f"   Query: {args.query[:80]}{'...' if len(args.query) > 80 else ''}")
            if context:
                print(f"   Context: {len(context)} chars from {args.file}")
            print("   💡 Start backend with: uvicorn main:app --reload")
            print("   Then use the web UI or curl to chat.")

    if args.json:
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()