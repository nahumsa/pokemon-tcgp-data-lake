import pytest
from unittest.mock import MagicMock, patch
from pokemon_cli.config import ChatConfig
from pokemon_cli.gateways.strategies.ollama import OllamaStrategy

@pytest.fixture
def config():
    return ChatConfig(
        api_key="none", 
        provider="ollama", 
        model_name="qwen3:8b",
        ollama_base_url="http://localhost:11434"
    )

@pytest.fixture
def ollama_strategy(config):
    with patch("pokemon_cli.gateways.strategies.ollama.Client"):
        return OllamaStrategy(config)

def test_ollama_thinking_extraction(ollama_strategy):
    """Test that <think> tags are correctly extracted from Ollama responses."""
    mock_response = MagicMock()
    # Simulate a response from a model like DeepSeek-R1
    mock_response.message.content = "<think>I need to check the tournament data for Pikachu decks.</think>Based on the latest data, Pikachu-EX is performing well."
    mock_response.message.tool_calls = []
    ollama_strategy.client.chat.return_value = mock_response

    response = ollama_strategy.generate_response("How is Pikachu doing?", [])

    assert response.thought == "I need to check the tournament data for Pikachu decks."
    assert response.text == "Based on the latest data, Pikachu-EX is performing well."

def test_ollama_no_thinking(ollama_strategy):
    """Test that responses without <think> tags are handled correctly."""
    mock_response = MagicMock()
    mock_response.message.content = "Pikachu is doing great!"
    mock_response.message.tool_calls = []
    ollama_strategy.client.chat.return_value = mock_response

    response = ollama_strategy.generate_response("How is Pikachu doing?", [])

    assert response.thought is None
    assert response.text == "Pikachu is doing great!"
