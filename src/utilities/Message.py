from dataclasses import dataclass
from typing import Optional

@dataclass
class Message:
    role: str
    content: str
    name: Optional[str] = None

    def to_string(self) -> str:
        return f"{self.name} -> {self.content}"
