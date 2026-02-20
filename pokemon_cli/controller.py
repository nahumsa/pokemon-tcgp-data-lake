import logging
from typing import List, Any
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from pokemon_cli.gateways.mcp import MCPGateway
from pokemon_cli.gateways.llm import LLMGateway
from pokemon_cli.models import LLMResponse, ToolCall

logger = logging.getLogger("pokemon-cli")
console = Console()


class AnalystController:
    """
    Controller pattern: Orchestrates the conversation flow.
    """

    def __init__(self, mcp: MCPGateway, llm: LLMGateway):
        self.mcp = mcp
        self.llm = llm
        self.tools: Any = None
        self.tool_count: int = 0

    async def initialize(self):
        """Prepare the gateways for operation."""
        await self.mcp.connect()
        mcp_tools = await self.mcp.get_tools()
        self.tools = self.llm.prepare_tools(mcp_tools)
        self.tool_count = len(mcp_tools)
        logger.info(f"Analysis Controller initialized with {self.tool_count} tools")

    def _get_thought_panel(self, thought: str) -> Panel:
        """Create a panel for the thinking process."""
        return Panel(thought, title="[bold blue]Thinking[/bold blue]", border_style="blue", padding=(1, 2))

    async def handle_user_query(self, message: str):
        """Process a user message, handling any required tool cycles."""
        with console.status("[bold blue]Thinking...[/bold blue]"):
            response = self.llm.generate_response(message, self.tools)

        while True:
            if not response.tool_calls:
                # For the final answer, show thought briefly if it exists then remove it
                if response.thought:
                    with Live(self._get_thought_panel(response.thought), console=console, transient=True):
                        import time
                        time.sleep(0.5) # Brief pause so it's not a flash
                
                if response.text:
                    console.print(f"\n[bold green]AI:[/bold green] {response.text}")
                break

            tool_outputs = []
            
            # Show the thought process while tools are executing!
            # It will disappear when this block exits.
            with Live(self._get_thought_panel(response.thought) if response.thought else "", 
                     console=console, transient=True) as live:
                for call in response.tool_calls:
                    console.print(f"[bold yellow][*] AI calling tool:[/bold yellow] {call.name}({call.args})")
                    try:
                        result_text = await self.mcp.call_tool(call.name, call.args)
                    except Exception as e:
                        logger.error(f"Tool execution failed: {call.name}", exc_info=True)
                        result_text = f"Error executing tool: {str(e)}"

                    tool_outputs.append({"name": call.name, "output": result_text})

            # Feed tool outputs back to the model and get next turn response
            with console.status("[bold blue]Thinking...[/bold blue]"):
                response = self.llm.add_tool_outputs(tool_outputs, self.tools)
