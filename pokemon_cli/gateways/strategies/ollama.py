import re
from typing import List, Any, Dict, Optional
from ollama import Client, ResponseError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from pokemon_cli.config import ChatConfig
from pokemon_cli.models import LLMResponse, ToolCall
from pokemon_cli.gateways.strategies.base import LLMStrategy

class OllamaStrategy(LLMStrategy):
    """
    Ollama implementation of the LLM strategy.
    """

    def __init__(self, config: ChatConfig):
        self.config = config
        self.client = Client(host=config.ollama_base_url)
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": config.system_prompt}
        ]

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(ResponseError),
    )
    def _chat_with_retry(self, **kwargs) -> Any:
        return self.client.chat(**kwargs)

    def prepare_tools(self, mcp_tools: List[Any]) -> List[Dict[str, Any]]:
        # Ollama uses OpenAI-style tool definitions
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema,
                },
            }
            for t in mcp_tools
        ]

    def _convert_response(self, response: Any) -> LLMResponse:
        message = response.message
        content = message.content or ""
        tool_calls = []
        
        # Check for thinking process in <think> tags (common in DeepSeek-R1, Llama-3-Thinking, etc.)
        thought = None
        text = content
        
        think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL)
        if think_match:
            thought = think_match.group(1).strip()
            text = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        name=tc.function.name,
                        args=tc.function.arguments
                    )
                )
        
        return LLMResponse(
            text=text,
            thought=thought,
            tool_calls=tool_calls
        )

    def generate_response(self, user_input: str, tools: Any) -> LLMResponse:
        self.history.append({"role": "user", "content": user_input})
        
        response = self._chat_with_retry(
            model=self.config.model_name,
            messages=self.history,
            tools=tools,
        )
        
        # Add assistant response to history
        self.history.append({
            "role": "assistant",
            "content": response.message.content,
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in getattr(response.message, 'tool_calls', []) or []
            ] if hasattr(response.message, 'tool_calls') and response.message.tool_calls else None
        })
        
        return self._convert_response(response)

    def add_tool_outputs(
        self, tool_outputs: List[Dict[str, Any]], tools: Any
    ) -> LLMResponse:
        for output in tool_outputs:
            self.history.append({
                "role": "tool",
                "content": str(output["output"]),
                "name": output["name"]
            })

        response = self._chat_with_retry(
            model=self.config.model_name,
            messages=self.history,
            tools=tools,
        )
        
        # Add assistant response to history
        self.history.append({
            "role": "assistant",
            "content": response.message.content,
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in getattr(response.message, 'tool_calls', []) or []
            ] if hasattr(response.message, 'tool_calls') and response.message.tool_calls else None
        })
        
        return self._convert_response(response)
