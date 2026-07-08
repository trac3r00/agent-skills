def utility_gate(payload: str) -> str:
    if payload is None:
        return ""
    return str(payload).strip().lower()


class UtilityGate:
    def __init__(self):
        self.prefix = "utility"
