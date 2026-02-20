import asyncio
import os
import logging
import traceback
from rich.console import Console
from pokemon_cli.config import ChatConfig
from pokemon_cli.gateways.mcp import MCPGateway
from pokemon_cli.gateways.llm import LLMGateway
from pokemon_cli.controller import AnalystController

logger = logging.getLogger("pokemon-cli")
console = Console()


async def run_chat_session():
    """Main entry point for the chat session."""
    api_key = os.environ.get("GEMINI_API_KEY")
    config = ChatConfig(api_key=api_key)

    if not api_key and config.provider.lower() == "gemini":
        console.print("[bold red]Error: GEMINI_API_KEY environment variable not set.[/bold red]")
        return

    mcp_gateway = MCPGateway(config)
    llm_gateway = LLMGateway(config)
    controller = AnalystController(mcp_gateway, llm_gateway)

    try:
        await controller.initialize()

        console.print("\n[bold cyan]=== Pokemon TCG Semantic Chat ===[/bold cyan]")
        console.print(f"Connected. {controller.tool_count} tools available.")
        console.print("Type 'exit' or 'quit' to stop.")

        while True:
            try:
                user_input = console.input("\n[bold]You:[/bold] ").strip()
                if user_input.lower() in ["exit", "quit"]:
                    break
                if not user_input:
                    continue

                await controller.handle_user_query(user_input)

            except EOFError:
                break
            except Exception as e:
                logger.exception("Uncaught error during interaction")
                console.print(f"\n[bold red]An error occurred:[/bold red] {e}")

    finally:
        await mcp_gateway.disconnect()


def main():
    """CLI script execution entry point."""
    try:
        asyncio.run(run_chat_session())
    except KeyboardInterrupt:
        print("\nBye!")
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
