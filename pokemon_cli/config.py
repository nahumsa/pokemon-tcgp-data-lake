import sys
import logging
from typing import List
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("pokemon-cli")


@dataclass
class ChatConfig:
    """Enterprise configuration object."""

    api_key: str
    provider: str = "gemini"
    model_name: str = "gemini-3-flash-preview"
    ollama_base_url: str = "http://localhost:11434"
    system_prompt: str = (
        "You are an expert Pokemon TCG Analyst. "
        "You have access to a semantic layer via tools that allow you to query tournament data, "
        "archetype performance, and card usage.\n\n"
        "Always use the available tools to answer questions about:\n"
        "1. Deck archetypes and their win rates.\n"
        "2. Card staples and inclusion rates.\n"
        "3. Matchup performance between archetypes.\n"
        "4. Specific match results."
    )
    mcp_command: str = "python"
    mcp_args: List[str] = field(
        default_factory=lambda: ["semantic_layer/semantic_layer/mcp_server.py"]
    )
