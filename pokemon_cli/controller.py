import logging
from typing import List
from google.genai import types
from pokemon_cli.gateways.mcp import MCPGateway
from pokemon_cli.gateways.llm import LLMGateway

logger = logging.getLogger("pokemon-cli")


class AnalystController:
    """
    Controller pattern: Orchestrates the conversation flow.
    """

    def __init__(self, mcp: MCPGateway, llm: LLMGateway):
        self.mcp = mcp
        self.llm = llm
        self.tools: List[types.Tool] = []

    async def initialize(self):
        """Prepare the gateways for operation."""
        await self.mcp.connect()
        mcp_tools = await self.mcp.get_tools()
        self.tools = self.llm.prepare_tools(mcp_tools)
        logger.info(f"Analysis Controller initialized with {len(mcp_tools)} tools")

    async def handle_user_query(self, message: str):
        """Process a user message, handling any required tool cycles."""
        response = self.llm.generate_response(message, self.tools)

        while True:
            # Extract function calls from the model's response
            tool_calls = [
                p.function_call
                for p in response.candidates[0].content.parts
                if p.function_call
            ]

            if not tool_calls:
                print(f"\nGemini: {response.text}")
                break

            tool_outputs = []
            for call in tool_calls:
                print(f"[*] AI calling tool: {call.name}({call.args})")
                try:
                    result_text = await self.mcp.call_tool(call.name, call.args)
                except Exception as e:
                    logger.error(f"Tool execution failed: {call.name}", exc_info=True)
                    result_text = f"Error executing tool: {str(e)}"

                tool_outputs.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=call.name, response={"result": result_text}
                        )
                    )
                )

            # Feed tool outputs back to the model
            self.llm.add_tool_outputs(tool_outputs)

            # Request next response based on new tool data
            response = self.llm.client.models.generate_content(
                model=self.llm.config.model_name,
                contents=self.llm.history,
                config=types.GenerateContentConfig(
                    system_instruction=self.llm.config.system_prompt,
                    tools=self.tools,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
            self.llm.history.append(response.candidates[0].content)
