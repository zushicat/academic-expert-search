from typing import Dict, Any

# from pydantic import BaseModel

# from settings import config


class SimpleRequest:
    def __init__(self, number: int, text: str, boolean: bool):
        self.number = number
        self.text = text
        self.boolean = boolean

    def get_processed_data(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "text": self.text if self.text else None,
            "boolean": self.boolean,
        }
