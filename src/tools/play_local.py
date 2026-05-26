#!/usr/bin/env python3
"""
학생 대국 연습 도구.

직접 둔 수와 작성한 AI의 수를 번갈아 적용하면서 로컬에서 빠르게 확인한다.
"""

import argparse
import os
import time
import traceback
from typing import List, Optional, Set, Tuple

from connect6.yukmok import YukmokState
from tools.local_test_runner import load_agent_module, run_preflight, strict_parse_moves

Move = Tuple[int, int]


def board_to_text(state: YukmokState, last_moves: Optional[Set[Move]] = None) -> str:
    last_moves = last_moves or set()
    symbols = {0: ".", 1: "X", -1: "O"}
    lines = []
    size = state.board_size
    lines.append("     " + " ".join(f"{col:02d}" for col in range(size)))
    for row in range(size):
        cells = []
        for col in range(size):
            value = int(state.game_board[row, col])
            symbol = symbols.get(value, "?")
            if (row, col) in last_moves:
                symbol = symbol.lower()
            cells.append(f" {symbol}")
        lines.append(f"{row:02d}  " + " ".join(cells))
    lines.append("")
    lines.append("X: black, O: white, lowercase: last move")
    return "\n".join(lines)


def parse_human_line(raw: str, expected_count: int) -> Optional[List[Move]]:
    cleaned = raw.replace(",", " ").replace(";", " ").strip()
    if not cleaned:
        return None

    parts = cleaned.split()
    if len(parts) != expected_count * 2:
        return None

    try:
        values = [int(part) for part in parts]
    except ValueError:
        return None

    moves: List[Move] = []
    for idx in range(0, len(values), 2):
        moves.append((values[idx], values[idx + 1]))
    return moves


def status_to_winner(status: Optional[int]) -> Optional[str]:
    if status == 1:
        return "black(X)"
    if status == 2:
        return "white(O)"
    if status == 3:
        return "draw"
    return None


def apply_moves(state: YukmokState, moves: List[Move]) -> Optional[str]:
    for row, col in moves:
        if not state.is_valid_position(col, row):
            return f"invalid move: ({row}, {col})"
        state.update(col, row)
        winner = status_to_winner(state.check_status())
        if winner:
            return f"game_end:{winner}"
    return None


def prompt_human_moves(state: YukmokState, expected_count: int) -> Optional[List[Move]]:
    while True:
        suffix = "row col" if expected_count == 1 else "row1 col1 row2 col2"
        raw = input(f"Your move ({suffix}) > ").strip()
        lowered = raw.lower()
        if lowered in {"q", "quit", "exit"}:
            return None
        if lowered in {"h", "help", "?"}:
            print("좌표는 0부터 시작합니다. 예: 7 7 또는 7 7 7 8")
            continue

        moves = parse_human_line(raw, expected_count)
        if moves is None:
            print(f"입력 형식이 맞지 않습니다. {expected_count}개 돌의 row col을 입력하세요.")
            continue

        parsed, reason, detail = strict_parse_moves(moves, expected_count, state.board_size)
        if reason is not None or parsed is None:
            print(detail)
            continue

        occupied = [
            move for move in parsed
            if not state.is_valid_position(move[1], move[0])
        ]
        if occupied:
            print(f"이미 돌이 있거나 둘 수 없는 위치입니다: {occupied[0]}")
            continue

        return parsed


def run_game(agent_path: str, human_color: str, timeout: float, max_turns: int) -> int:
    agent = load_agent_module(agent_path)
    preflight = run_preflight(agent)
    if not preflight.get("ok"):
        print("AI 코드가 strict 검증을 통과하지 못했습니다.")
        for check in preflight.get("return_checks") or []:
            if not check.get("ok"):
                print(check.get("message") or check.get("reason"))
                break
        return 1

    human_player = 1 if human_color == "black" else -1
    ai_player = -human_player
    state = YukmokState()
    last_moves: Set[Move] = set()

    print("=== Connect6 Local Play ===")
    print("좌표 형식: row col (예: 7 7)")
    print("두 개를 두는 턴: row1 col1 row2 col2 (예: 7 7 7 8)")
    print("종료: q")
    print(f"Human: {'black(X)' if human_player == 1 else 'white(O)'}")
    print(f"AI: {'black(X)' if ai_player == 1 else 'white(O)'}")
    print()

    for turn_index in range(1, max_turns + 1):
        print(board_to_text(state, last_moves))
        expected_count = state.get_remaining_stones()
        player = state.turn
        current_moves: List[Move]

        if player == human_player:
            moves = prompt_human_moves(state, expected_count)
            if moves is None:
                print("연습 대국을 종료합니다.")
                return 0
            current_moves = moves
            last_moves = set(current_moves)
        else:
            print(f"AI thinking... ({expected_count} stone{'s' if expected_count > 1 else ''})")
            started = time.perf_counter()
            try:
                raw_moves = agent.act(state.clone(), num_stones=expected_count)
            except Exception:
                print("AI 실행 중 오류가 발생했습니다.")
                print(traceback.format_exc(limit=5))
                return 1

            elapsed = time.perf_counter() - started
            if elapsed > timeout:
                print(f"AI timeout: {elapsed:.3f}s > {timeout:.3f}s")
                return 1

            moves, reason, detail = strict_parse_moves(raw_moves, expected_count, state.board_size)
            if reason is not None or moves is None:
                print(f"AI 반환 형식 오류: {detail}")
                return 1

            occupied = [
                move for move in moves
                if not state.is_valid_position(move[1], move[0])
            ]
            if occupied:
                print(f"AI가 이미 돌이 있는 위치를 선택했습니다: {occupied[0]}")
                return 1

            current_moves = moves
            last_moves = set(current_moves)
            print(f"AI move: {moves} ({elapsed * 1000:.1f}ms)")

        result = apply_moves(state, current_moves)
        if result:
            print(board_to_text(state, last_moves))
            if result.startswith("game_end:"):
                winner = result.split(":", 1)[1]
                print(f"Game over: {winner}")
                return 0
            print(result)
            return 1

        if state.num_stones >= state.board_size * state.board_size:
            print(board_to_text(state, last_moves))
            print("Game over: draw")
            return 0

        if turn_index >= max_turns:
            print("최대 턴에 도달했습니다.")
            return 0

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", help="대국할 AI 파일 경로")
    parser.add_argument(
        "--human",
        choices=["black", "white"],
        default="black",
        help="사람이 둘 색상 (default: black)",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="AI 한 턴 제한 시간(초)")
    parser.add_argument("--max-turns", type=int, default=300, help="최대 턴 수")
    args = parser.parse_args()

    agent_path = args.agent
    if not os.path.isabs(agent_path):
        agent_path = os.path.abspath(agent_path)
    if not os.path.exists(agent_path):
        print(f"agent file not found: {agent_path}")
        return 1

    return run_game(agent_path, args.human, args.timeout, args.max_turns)


if __name__ == "__main__":
    raise SystemExit(main())
