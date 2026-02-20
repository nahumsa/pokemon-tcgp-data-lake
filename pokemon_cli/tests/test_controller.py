import pytest
from unittest.mock import MagicMock, AsyncMock
from pokemon_cli.controller import AnalystController
from pokemon_cli.models import LLMResponse, ToolCall


@pytest.fixture
def mock_gateways():
    mcp = MagicMock()
    mcp.connect = AsyncMock()
    mcp.get_tools = AsyncMock(return_value=[])
    mcp.call_tool = AsyncMock(return_value="tool output")

    llm = MagicMock()
    llm.prepare_tools = MagicMock(return_value=[])
    llm.generate_response = MagicMock()
    llm.add_tool_outputs = MagicMock()

    return mcp, llm


@pytest.mark.asyncio
async def test_controller_initialization(mock_gateways):
    mcp, llm = mock_gateways
    controller = AnalystController(mcp, llm)

    await controller.initialize()

    mcp.connect.assert_called_once()
    mcp.get_tools.assert_called_once()
    llm.prepare_tools.assert_called_once()


@pytest.mark.asyncio
async def test_handle_user_query_no_tools(mock_gateways):
    mcp, llm = mock_gateways
    controller = AnalystController(mcp, llm)

    # Mock response with no tool calls
    llm.generate_response.return_value = LLMResponse(text="Hello!", tool_calls=[])

    await controller.handle_user_query("hi")

    llm.generate_response.assert_called_once_with("hi", controller.tools)
    mcp.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_handle_user_query_with_tool_call(mock_gateways):
    mcp, llm = mock_gateways
    controller = AnalystController(mcp, llm)

    # First response has a tool call
    resp1 = LLMResponse(tool_calls=[ToolCall(name="test_tool", args={"a": 1})])

    # Second response (after tool) has text
    resp2 = LLMResponse(text="Done", tool_calls=[])

    llm.generate_response.return_value = resp1
    llm.add_tool_outputs.return_value = resp2

    await controller.handle_user_query("run tool")

    mcp.call_tool.assert_called_once_with("test_tool", {"a": 1})
    llm.add_tool_outputs.assert_called_once()
