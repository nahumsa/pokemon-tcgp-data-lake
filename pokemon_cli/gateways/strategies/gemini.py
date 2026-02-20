from typing import List, Any, Dict
from google import genai
from google.genai import types, errors
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from pokemon_cli.config import ChatConfig
from pokemon_cli.models import LLMResponse, ToolCall
from pokemon_cli.gateways.strategies.base import LLMStrategy

class GeminiStrategy(LLMStrategy):
    """
    Gemini implementation of the LLM strategy.
    """

    def __init__(self, config: ChatConfig):
        self.config = config
        self.client = genai.Client(api_key=config.api_key)
        self.history: List[types.Content] = []

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(errors.ServerError),
    )
    def _generate_with_retry(self, **kwargs) -> types.GenerateContentResponse:
        return self.client.models.generate_content(**kwargs)

    def prepare_tools(self, mcp_tools: List[Any]) -> List[types.Tool]:
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
        if not isinstance(schema, dict):
            return schema
        cleaned = {}
        for k, v in schema.items():
            if k in ["additionalProperties", "additional_properties"]:
                continue
            if k == "anyOf":
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

    def _convert_response(
        self, response: types.GenerateContentResponse
    ) -> LLMResponse:
        candidate = response.candidates[0]
        tool_calls = [
            ToolCall(name=p.function_call.name, args=p.function_call.args)
            for p in candidate.content.parts
            if p.function_call
        ]
        
        # Extract thinking process if available
        thoughts = [p.text for p in candidate.content.parts if p.thought]
        thought = "\n".join(thoughts) if thoughts else None
        
        return LLMResponse(text=response.text, thought=thought, tool_calls=tool_calls)

    def generate_response(self, user_input: str, tools: Any) -> LLMResponse:
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

        response = self._generate_with_retry(
            model=self.config.model_name, contents=self.history, config=gen_config
        )
        self.history.append(response.candidates[0].content)
        return self._convert_response(response)

    def add_tool_outputs(
        self, tool_outputs: List[Dict[str, Any]], tools: Any
    ) -> LLMResponse:
        parts = [
            types.Part(
                function_response=types.FunctionResponse(
                    name=o["name"], response={"result": o["output"]}
                )
            )
            for o in tool_outputs
        ]
        self.history.append(types.Content(role="model", parts=parts))

        # Request next response based on new tool data
        response = self._generate_with_retry(
            model=self.config.model_name,
            contents=self.history,
            config=types.GenerateContentConfig(
                system_instruction=self.config.system_prompt,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    disable=True
                ),
            ),
        )
        self.history.append(response.candidates[0].content)
        return self._convert_response(response)
