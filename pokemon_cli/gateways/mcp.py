import os
import logging
from typing import List, Any, Dict, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pokemon_cli.config import ChatConfig

logger = logging.getLogger("pokemon-cli")


class MCPGateway:
    """
    Gateway pattern: Encapsulates the Model Context Protocol communication.
    """

    def __init__(self, config: ChatConfig):
        self.params = StdioServerParameters(
            command=config.mcp_command,
            args=config.mcp_args,
            env={**os.environ, "PYTHONPATH": os.getcwd()},
        )
        self._client_context = None
        self.session: Optional[ClientSession] = None

    async def connect(self):
        """Initializes the connection via stdio."""
        self._client_context = stdio_client(self.params)
        read, write = await self._client_context.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        await self.session.initialize()
        logger.info("Connected to MCP Server")

    async def disconnect(self):
        """Clean shutdown of transport resources."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self._client_context:
            await self._client_context.__aexit__(None, None, None)

    async def get_tools(self) -> List[Any]:
        """Fetch available tools from the MCP server."""
        if not self.session:
            raise RuntimeError("MCP Session not initialized")
        response = await self.session.list_tools()
        return response.tools

    async def call_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Execute a tool and return the consolidated text result."""
        if not self.session:
            raise RuntimeError("MCP Session not initialized")
        result = await self.session.call_tool(name, args)
        return "\n".join([c.text for c in result.content if hasattr(c, "text")])  # type: ignore
