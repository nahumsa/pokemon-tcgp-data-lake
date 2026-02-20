from typing import List, Any, Dict
from pokemon_cli.config import ChatConfig
from pokemon_cli.models import LLMResponse
from pokemon_cli.gateways.strategies.base import LLMStrategy
from pokemon_cli.gateways.strategies.gemini import GeminiStrategy
from pokemon_cli.gateways.strategies.openai import OpenAIStrategy
from pokemon_cli.gateways.strategies.ollama import OllamaStrategy

class LLMGateway:
    """
    Gateway pattern: Encapsulates the chosen LLM strategy.
    """

    def __init__(self, config: ChatConfig):
        self.config = config
        self.strategy = self._get_strategy()

    def _get_strategy(self) -> LLMStrategy:
        if self.config.provider == "gemini":
            return GeminiStrategy(self.config)
        elif self.config.provider == "openai":
            return OpenAIStrategy(self.config)
        elif self.config.provider == "ollama":
            return OllamaStrategy(self.config)
        else:
            raise ValueError(f"Unknown LLM provider: {self.config.provider}")

    def prepare_tools(self, mcp_tools: List[Any]) -> Any:
        return self.strategy.prepare_tools(mcp_tools)

    def generate_response(self, user_input: str, tools: Any) -> LLMResponse:
        return self.strategy.generate_response(user_input, tools)

    def add_tool_outputs(
        self, tool_outputs: List[Dict[str, Any]], tools: Any
    ) -> LLMResponse:
        return self.strategy.add_tool_outputs(tool_outputs, tools)
