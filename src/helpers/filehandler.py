import json
import os
from typing import Any, Dict

DATA_DIR = os.environ["DATA_DIR"]


def read_json_file(file_path: str) -> Dict[str, Any]:
    with open(f"{DATA_DIR}/{file_path}", "r") as f:
        return json.load(f)


def read_text_file(file_path: str) -> Dict[str, Any]:
    with open(f"{DATA_DIR}/{file_path}", "r") as f:
        return f.read()


def write_json_file(file_path: str, data: Dict[str, Any]) -> None:
    with open(f"{DATA_DIR}/{file_path}", "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_text_file(file_path: str, data: Dict[str, Any]) -> None:
    with open(f"{DATA_DIR}/{file_path}", "w") as f:
        f.write(data)
