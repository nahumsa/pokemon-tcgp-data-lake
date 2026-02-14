import pytest
from unittest.mock import MagicMock, AsyncMock
from pokemon_cli.controller import AnalystController

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
    llm.client = MagicMock()
    llm.config = MagicMock()
    llm.history = []
    
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
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [MagicMock(function_call=None, text="Hello!")]
    mock_response.text = "Hello!"
    llm.generate_response.return_value = mock_response
    
    await controller.handle_user_query("hi")
    
    llm.generate_response.assert_called_once_with("hi", [])
    mcp.call_tool.assert_not_called()

@pytest.mark.asyncio
async def test_handle_user_query_with_tool_call(mock_gateways):
    mcp, llm = mock_gateways
    controller = AnalystController(mcp, llm)
    
    # First response has a tool call
    tool_call = MagicMock()
    tool_call.name = "test_tool"
    tool_call.args = {"a": 1}
    
    part_with_call = MagicMock()
    part_with_call.function_call = tool_call
    
    resp1 = MagicMock()
    resp1.candidates = [MagicMock()]
    resp1.candidates[0].content.parts = [part_with_call]
    
    # Second response (after tool) has text
    resp2 = MagicMock()
    resp2.candidates = [MagicMock()]
    resp2.candidates[0].content.parts = [MagicMock(function_call=None, text="Done")]
    resp2.text = "Done"
    
    llm.generate_response.return_value = resp1
    llm.client.models.generate_content.return_value = resp2
    
    await controller.handle_user_query("run tool")
    
    mcp.call_tool.assert_called_once_with("test_tool", {"a": 1})
    llm.add_tool_outputs.assert_called_once()
