import asyncio
import os
import logging
import traceback
from pokemon_cli.config import ChatConfig
from pokemon_cli.gateways.mcp import MCPGateway
from pokemon_cli.gateways.llm import LLMGateway
from pokemon_cli.controller import AnalystController

logger = logging.getLogger("pokemon-cli")


async def run_chat_session():
    """Main entry point for the chat session."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        return

    config = ChatConfig(api_key=api_key)
    mcp_gateway = MCPGateway(config)
    llm_gateway = LLMGateway(config)
    controller = AnalystController(mcp_gateway, llm_gateway)

    try:
        await controller.initialize()

        print("\n=== Pokemon TCG Semantic Chat ===")
        print(
            f"Connected. {len(controller.tools[0].function_declarations)} tools available."
        )
        print("Type 'exit' or 'quit' to stop.")

        while True:
            try:
                user_input = input("\nYou: ").strip()
                if user_input.lower() in ["exit", "quit"]:
                    break
                if not user_input:
                    continue

                await controller.handle_user_query(user_input)

            except EOFError:
                break
            except Exception as e:
                logger.exception("Uncaught error during interaction")
                print(f"\nAn error occurred: {e}")

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
