import pytest
from unittest.mock import MagicMock, patch
from pokemon_cli.config import ChatConfig
from pokemon_cli.gateways.llm import LLMGateway
from google.genai import types

@pytest.fixture
def config():
    return ChatConfig(api_key="test_key")

@pytest.fixture
def llm_gateway(config):
    # Patch genai.Client to avoid real API calls during init
    with patch("google.genai.Client"):
        return LLMGateway(config)

def test_clean_schema(llm_gateway):
    """Test that the schema cleaner removes problematic keys for Gemini."""
    dirty_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"}
        },
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }
    
    clean = llm_gateway._clean_schema(dirty_schema)
    
    assert "additionalProperties" not in clean
    assert "anyOf" not in clean
    assert clean["type"] == "string" # anyOf simplified
    assert clean["properties"]["name"]["type"] == "string"

def test_prepare_tools(llm_gateway):
    """Test conversion from MCP tool to Gemini tool."""
    mcp_tool = MagicMock()
    mcp_tool.name = "get_stats"
    mcp_tool.description = "Get stats"
    mcp_tool.inputSchema = {"type": "object", "properties": {}}
    
    tools = llm_gateway.prepare_tools([mcp_tool])
    
    assert len(tools) == 1
    assert isinstance(tools[0], types.Tool)
    assert tools[0].function_declarations[0].name == "get_stats"

def test_generate_response_updates_history(llm_gateway):
    """Test that generating a response appends to history."""
    mock_response = MagicMock()
    mock_response.candidates = [MagicMock(content="assistant response")]
    llm_gateway.client.models.generate_content.return_value = mock_response
    
    llm_gateway.generate_response("hello", [])
    
    assert len(llm_gateway.history) == 2
    assert llm_gateway.history[0].role == "user"
    assert llm_gateway.history[0].parts[0].text == "hello"
