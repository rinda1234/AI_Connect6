#!/usr/bin/env python3
"""
제출 전 빠른 인터페이스 검증 도구.

사용:
    uv run python check_submission.py agent_template.py
"""

import argparse
import os
import sys

from tools.local_test_runner import load_agent_module, run_preflight, print_preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", help="검증할 에이전트 파일 경로")
    args = parser.parse_args()

    agent_path = args.agent
    if not os.path.isabs(agent_path):
        agent_path = os.path.abspath(agent_path)

    if not os.path.exists(agent_path):
        print(f"agent file not found: {agent_path}")
        return 1

    try:
        module = load_agent_module(agent_path)
    except Exception as exc:
        print("=== Step 1. 로컬 검증 (Strict) ===")
        print("Import: FAIL")
        print(f"- {exc}")
        return 1

    preflight = run_preflight(module)
    print_preflight(preflight)

    if not preflight.get("ok"):
        print()
        print("검증 실패")
        return 1

    print()
    print("검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
