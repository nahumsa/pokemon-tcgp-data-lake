import pytest
from unittest.mock import MagicMock, patch
from pokemon_cli.config import ChatConfig
from pokemon_cli.gateways.llm import LLMGateway
from pokemon_cli.gateways.strategies.gemini import GeminiStrategy
from pokemon_cli.gateways.strategies.openai import OpenAIStrategy
from pokemon_cli.models import LLMResponse
from google.genai import types


@pytest.fixture
def config():
    return ChatConfig(api_key="test_key", provider="gemini")


@pytest.fixture
def gemini_strategy(config):
    # Patch genai.Client to avoid real API calls during init
    with patch("google.genai.Client"):
        return GeminiStrategy(config)


def test_gemini_clean_schema(gemini_strategy):
    """Test that the schema cleaner removes problematic keys for Gemini."""
    dirty_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"name": {"type": "string"}},
        "anyOf": [{"type": "string"}, {"type": "null"}],
    }

    clean = gemini_strategy._clean_schema(dirty_schema)

    assert "additionalProperties" not in clean
    assert "anyOf" not in clean
    assert clean["type"] == "string"  # anyOf simplified
    assert clean["properties"]["name"]["type"] == "string"


def test_gemini_prepare_tools(gemini_strategy):
    """Test conversion from MCP tool to Gemini tool."""
    mcp_tool = MagicMock()
    mcp_tool.name = "get_stats"
    mcp_tool.description = "Get stats"
    mcp_tool.inputSchema = {"type": "object", "properties": {}}

    tools = gemini_strategy.prepare_tools([mcp_tool])

    assert len(tools) == 1
    assert isinstance(tools[0], types.Tool)
    assert tools[0].function_declarations[0].name == "get_stats"


def test_gemini_generate_response_updates_history(gemini_strategy):
    """Test that generating a response appends to history."""
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock()]
    mock_response.candidates[0].content.parts = [
        MagicMock(function_call=None, text="assistant response")
    ]
    mock_response.text = "assistant response"
    gemini_strategy.client.models.generate_content.return_value = mock_response

    gemini_strategy.generate_response("hello", [])

    assert len(gemini_strategy.history) == 2
    assert gemini_strategy.history[0].role == "user"
    assert gemini_strategy.history[0].parts[0].text == "hello"


def test_llm_gateway_selector(config):
    """Test that LLMGateway selects the correct strategy."""
    with patch("google.genai.Client"):
        gateway = LLMGateway(config)
        assert isinstance(gateway.strategy, GeminiStrategy)

    config.provider = "openai"
    gateway = LLMGateway(config)
    assert isinstance(gateway.strategy, OpenAIStrategy)
