import pytest
from unittest.mock import MagicMock, patch
from pokemon_cli.config import ChatConfig
from pokemon_cli.gateways.strategies.ollama import OllamaStrategy
from pokemon_cli.models import ToolCall

@pytest.fixture
def config():
    return ChatConfig(
        api_key="none", 
        provider="ollama", 
        model_name="llama3.1",
        ollama_base_url="http://localhost:11434"
    )

@pytest.fixture
def ollama_strategy(config):
    with patch("pokemon_cli.gateways.strategies.ollama.Client"):
        return OllamaStrategy(config)

def test_ollama_prepare_tools(ollama_strategy):
    """Test conversion from MCP tool to Ollama tool format."""
    mcp_tool = MagicMock()
    mcp_tool.name = "get_archetype_stats"
    mcp_tool.description = "Get statistics for a deck archetype"
    mcp_tool.inputSchema = {
        "type": "object",
        "properties": {"archetype": {"type": "string"}}
    }

    tools = ollama_strategy.prepare_tools([mcp_tool])

    assert len(tools) == 1
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "get_archetype_stats"
    assert tools[0]["function"]["parameters"] == mcp_tool.inputSchema

def test_ollama_generate_response_updates_history(ollama_strategy):
    """Test that generating a response appends to history correctly."""
    mock_response = MagicMock()
    mock_response.message.content = "I can help with that."
    mock_response.message.tool_calls = []
    ollama_strategy.client.chat.return_value = mock_response

    ollama_strategy.generate_response("What is the best deck?", [])

    # History should have: system, user, assistant
    assert len(ollama_strategy.history) == 3
    assert ollama_strategy.history[1]["role"] == "user"
    assert ollama_strategy.history[1]["content"] == "What is the best deck?"
    assert ollama_strategy.history[2]["role"] == "assistant"
    assert ollama_strategy.history[2]["content"] == "I can help with that."

def test_ollama_tool_call_conversion(ollama_strategy):
    """Test that Ollama tool calls are correctly converted to our model."""
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "get_stats"
    mock_tool_call.function.arguments = {"archetype": "Pikachu"}
    
    mock_response = MagicMock()
    mock_response.message.content = ""
    mock_response.message.tool_calls = [mock_tool_call]
    ollama_strategy.client.chat.return_value = mock_response

    response = ollama_strategy.generate_response("Get stats for Pikachu", [])

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "get_stats"
    assert response.tool_calls[0].args == {"archetype": "Pikachu"}

def test_ollama_add_tool_outputs(ollama_strategy):
    """Test adding tool outputs to history and getting next response."""
    # Setup initial state
    ollama_strategy.history.append({"role": "user", "content": "test"})
    
    mock_response = MagicMock()
    mock_response.message.content = "Final answer"
    mock_response.message.tool_calls = []
    ollama_strategy.client.chat.return_value = mock_response

    tool_outputs = [{"name": "get_stats", "output": "{\"win_rate\": 0.6}"}]
    response = ollama_strategy.add_tool_outputs(tool_outputs, [])

    # History: system, user, tool, assistant
    assert any(h["role"] == "tool" for h in ollama_strategy.history)
    tool_msg = next(h for h in ollama_strategy.history if h["role"] == "tool")
    assert tool_msg["content"] == "{\"win_rate\": 0.6}"
    assert response.text == "Final answer"
