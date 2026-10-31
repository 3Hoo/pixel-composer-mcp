import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from pixel_composer_mcp import server


def test_expected_failures_reach_client_as_tool_error(tmp_path):
    # Without conversion the SDK replaces the message with a generic "Error executing tool".
    with pytest.raises(ToolError, match="missing.pxc"):
        server.inspect_project(str(tmp_path / "missing.pxc"))


def test_tool_schema_keeps_parameters():
    tools = {t.name: t for t in asyncio.run(server.mcp.list_tools())}
    assert set(tools["set_input"].input_schema["properties"]) >= {"node", "index", "value", "path", "reload"}


def test_add_node_refuses_dialog_types_without_touching_app():
    # These pop a modal file dialog on manual creation, which freezes the app's main loop.
    with pytest.raises(ToolError, match="Node_Image"):
        server.add_node("Node_Image")
