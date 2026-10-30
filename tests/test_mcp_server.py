"""Tests for Sentinel Model Context Protocol (MCP) Server."""
import json
import pytest
from sentinel.mcp_server import MCPServer, TOOLS


class DummyDB:
    pass


def test_mcp_initialize():
    server = MCPServer(DummyDB())
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {}
    }
    resp = server.handle_request(req)
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "meridian-sentinel-mcp"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_tools_list():
    server = MCPServer(DummyDB())
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    resp = server.handle_request(req)
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "list_machines" in tool_names
    assert "get_sensor_trends" in tool_names
    assert "get_prediction_evidence" in tool_names
    assert "draft_work_order" in tool_names

    # Assert dangerous operations are NOT in tools list
    assert "approve_work_order" not in tool_names
    assert "deploy_model" not in tool_names
    assert "shutdown_machine" not in tool_names


def test_mcp_unknown_tool_call():
    server = MCPServer(DummyDB())
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "approve_work_order",
            "arguments": {"work_order_id": "foo"}
        }
    }
    resp = server.handle_request(req)
    assert resp["id"] == 3
    assert "error" in resp
    assert "Unknown MCP tool" in resp["error"]["message"]

