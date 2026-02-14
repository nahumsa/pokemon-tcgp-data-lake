import logging
from typing import List, Any, Dict
from google import genai
from google.genai import types
from pokemon_cli.config import ChatConfig

logger = logging.getLogger("pokemon-cli")


class LLMGateway:
    """
    Gateway pattern: Encapsulates the Gemini GenAI SDK.
    """

    def __init__(self, config: ChatConfig):
        self.client = genai.Client(api_key=config.api_key)
        self.config = config
        self.history: List[types.Content] = []

    def prepare_tools(self, mcp_tools: List[Any]) -> List[types.Tool]:
        """Convert MCP tools to Gemini-compatible function declarations."""
        declarations = [
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=self._clean_schema(t.inputSchema),
            )
            for t in mcp_tools
        ]
        return [types.Tool(function_declarations=declarations)]

    def _clean_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively clean up JSON schema for Gemini API compatibility."""
        if not isinstance(schema, dict):
            return schema
        cleaned = {}
        for k, v in schema.items():
            if k in ["additionalProperties", "additional_properties"]:
                continue
            if k == "anyOf":
                # Simplify anyOf for Gemini: use the first non-null type
                types_list = [item for item in v if item.get("type") != "null"]
                if types_list:
                    cleaned.update(self._clean_schema(types_list[0]))
                    continue
            if isinstance(v, dict):
                cleaned[k] = self._clean_schema(v)
            elif isinstance(v, list):
                cleaned[k] = [
                    self._clean_schema(item) if isinstance(item, dict) else item
                    for item in v
                ]
            else:
                cleaned[k] = v
        return cleaned

    def generate_response(
        self, user_input: str, tools: List[types.Tool]
    ) -> types.GenerateContentResponse:
        """Generate a single turn of content."""
        self.history.append(
            types.Content(role="user", parts=[types.Part(text=user_input)])
        )

        gen_config = types.GenerateContentConfig(
            system_instruction=self.config.system_prompt,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        response = self.client.models.generate_content(
            model=self.config.model_name, contents=self.history, config=gen_config
        )
        self.history.append(response.candidates[0].content)
        return response

    def add_tool_outputs(self, tool_responses: List[types.Part]):
        """Record the results of tool executions into the chat history."""
        self.history.append(types.Content(role="model", parts=tool_responses))
