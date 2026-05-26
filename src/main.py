#!/usr/bin/env python3
"""Student package command entrypoint.

Usage:
    python main.py play agent_template.py
    python main.py check agent_template.py
    python main.py benchmark agent_template.py
"""

import sys
from typing import Callable, Dict, List


USAGE = """Connect6 AI local tools

Commands:
  play AGENT.py [--human black|white] [--timeout SEC] [--max-turns N]
      Play against your AI in the terminal.

  check AGENT.py
      Run the strict submission interface check.

  benchmark AGENT.py [runner options...]
      Run strict validation and local random-reference games.

  serve [runner server options...]
      Start the optional local HTTP runner for compatible web workflows.

Examples:
  uv run python main.py play agent_template.py
  uv run python main.py play agent_template.py --human white
  uv run python main.py check agent_template.py
  uv run python main.py benchmark agent_template.py --show-final-board
"""


def _run_with_argv(argv: List[str], target: Callable[[], int | None]) -> int:
    original = sys.argv[:]
    try:
        sys.argv = argv
        result = target()
        return int(result or 0)
    finally:
        sys.argv = original


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "help"}:
        print(USAGE)
        return 0

    command = sys.argv[1].strip().lower()
    args = sys.argv[2:]

    if command == "play":
        from tools.play_local import main as play_main

        return _run_with_argv(["play_local.py", *args], play_main)

    if command == "check":
        from tools.check_submission import main as check_main

        return _run_with_argv(["check_submission.py", *args], check_main)

    if command in {"benchmark", "bench", "test"}:
        from tools.local_test_runner import main as runner_main

        return _run_with_argv(["local_test_runner.py", *args], runner_main)

    if command == "serve":
        from tools.local_test_runner import main as runner_main

        return _run_with_argv(["local_test_runner.py", "--serve", *args], runner_main)

    print(f"Unknown command: {command}")
    print()
    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
