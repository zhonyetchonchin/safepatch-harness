from __future__ import annotations

import json
from dataclasses import asdict

from safepatch.demo.mock_scenarios import run_all_scenarios


def main() -> None:
    print(json.dumps([asdict(result) for result in run_all_scenarios()], indent=2))


if __name__ == "__main__":
    main()
