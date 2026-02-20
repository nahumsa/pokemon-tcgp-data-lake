from abc import ABC, abstractmethod
from typing import List, Any, Dict
from pokemon_cli.models import LLMResponse


class LLMStrategy(ABC):
    """
    Abstract base strategy for different LLM providers.
    """

    @abstractmethod
    def prepare_tools(self, mcp_tools: List[Any]) -> Any:
        pass

    @abstractmethod
    def generate_response(self, user_input: str, tools: Any) -> LLMResponse:
        pass

    @abstractmethod
    def add_tool_outputs(
        self, tool_outputs: List[Dict[str, Any]], tools: Any
    ) -> LLMResponse:
        pass
