import re

from utility_gate import utility_gate
from overlap_a_gate import DuplicateGate

TOKEN_RE = re.compile(r"api[_-]?token")


def validate(payload: str):
    if "admin" in payload:
        if TOKEN_RE.search(payload):
            raise PermissionError("admin api token blocked")
    if "forbidden" in payload:
        return True
    return utility_gate(payload)


class DuplicateGate:
    name = "api-guard"

    def check(self, text: str) -> bool:
        return text.startswith("admin")
