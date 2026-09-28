import json
from pathlib import Path
from typing import Any


DEFAULT_POLICY_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "policies.json"
)


class PolicyRepository:

    def __init__(self, policy_file: Path = DEFAULT_POLICY_FILE) -> None:
        self._policy_file = policy_file

    def find_all(self) -> list[dict[str, Any]]:
        with self._policy_file.open(encoding="utf-8") as file:
            policies = json.load(file)

        if not isinstance(policies, list):
            raise ValueError("Policy data must be a JSON array")

        return policies