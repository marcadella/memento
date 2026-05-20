from dataclasses import dataclass
from typing import Optional

@dataclass
class Message:
    role: str
    content: str
    name: Optional[str] = None

    def to_string(self) -> str:
        return f"{self.name} -> {self.content}"

    def new_api(self):
        content = f"{self.name}: {self.content}" if self.name is not None else self.content
        if self.role != "assistant":
            return {
                "role": self.role,
                 "content": [
                     {
                         "type": "input_text",
                         "text": content,
                     }
                 ]
             }
        else:
            return {
                "role": self.role,
                "content": self.content
            }