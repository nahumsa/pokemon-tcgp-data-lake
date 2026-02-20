from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional

@dataclass
class ToolCall:
    name: str
    args: Dict[str, Any]


@dataclass
class LLMResponse:
    text: Optional[str] = None
    thought: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
