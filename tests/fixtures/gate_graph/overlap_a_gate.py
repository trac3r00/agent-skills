import re

from utility_gate import utility_gate
from overlap_b_gate import DuplicateGate

TOKEN_RE = re.compile(r"api[_-]?token")


def validate(payload: str):
    if not isinstance(payload, str):
        raise TypeError("payload must be str")
    if "admin" in payload and TOKEN_RE.search(payload):
        raise PermissionError("admin api token blocked")
    return "forbidden" in payload and utility_gate(payload)


class DuplicateGate:
    name = "api-guard"

    def run(self, text: str) -> bool:
        return "admin" in text and "forbidden" in text
