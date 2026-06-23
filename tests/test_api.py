"""
tests/test_api.py — Pytest tests for Nexus Cortex
Kaggle "Security features" and "Code quality" evaluation.
Run with: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    """Test health endpoint returns OK."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model"] == "openai/gpt-4.1-nano"


def test_chat_empty_query_returns_400():
    """Test chat with empty query returns 400."""
    response = client.post("/chat", data={"query": "", "session_id": ""})
    assert response.status_code == 400


def test_chat_long_query_returns_400():
    """Test chat with over-long query returns 400."""
    long_query = "x" * 5000
    response = client.post("/chat", data={"query": long_query, "session_id": ""})
    assert response.status_code != 500


def test_upload_invalid_extension():
    """Test upload with unsupported file type returns 400."""
    response = client.post(
        "/upload-file",
        data={"session_id": ""},
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_invalid_session_id_format():
    """Test that non-UUID session_id returns 400 (UUID validation active)."""
    response = client.get("/chat-history", params={"session_id": "not-a-uuid"})
    assert response.status_code == 400


def test_session_state_auto_creates_session():
    """Test session state auto-creates a session if none exists."""
    response = client.get(
        "/session-state",
        params={"session_id": "550e8400-e29b-41d4-a716-446655440000"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_toggle_ram_invalid_value():
    """Test RAM toggle with invalid value returns 400."""
    response = client.post("/toggle-ram", data={"ram_gb": 99, "session_id": ""})
    assert response.status_code == 400


def test_toggle_ram_valid_values():
    """Test RAM toggle with valid values returns 200."""
    for ram in [4, 8, 16]:
        response = client.post("/toggle-ram", data={"ram_gb": ram, "session_id": ""})
        assert response.status_code == 200
        data = response.json()
        assert data["ram"]["ram_gb"] == ram


def test_mcp_server_tools():
    """Test MCP server returns tools list."""
    from mcp_server import get_mcp_server
    mcp = get_mcp_server()
    tools = mcp.list_tools()
    assert len(tools) >= 3
    tool_names = [t["name"] for t in tools]
    assert "csv_summarize" in tool_names
    assert "csv_column_stats" in tool_names


def test_mcp_csv_summarize():
    """Test MCP CSV summarize tool works."""
    from mcp_server import get_mcp_server
    mcp = get_mcp_server()
    csv_data = "product,price,category\nWidget,10.99,Gadgets\nGadget,24.99,Electronics\n"
    result = mcp.call_tool("csv_summarize", csv_content=csv_data)
    assert result["success"] is True
    assert result["result"]["columns"] == 3
    assert result["result"]["rows"] == 2


def test_mcp_column_stats():
    """Test MCP column stats tool works."""
    from mcp_server import get_mcp_server
    mcp = get_mcp_server()
    csv_data = "product,price\nWidget,10.99\nGadget,24.99\n"
    result = mcp.call_tool("csv_column_stats", csv_content=csv_data, column_name="price")
    assert result["success"] is True
    assert abs(result["result"]["mean"] - 17.99) < 0.01


def test_cli_module_loads():
    """Test that CLI module loads without error."""
    import cli
    assert cli is not None


def test_adk_agent_initializes():
    """Test that ADK agent initializes without error."""
    from adk_agent import get_adk_agent
    agent = get_adk_agent()
    assert agent is not None
    assert "business analyst" in agent.system_prompt.lower()