"""
학생 로컬 테스트 도구 (student_package 단독 실행 가능)

핵심 목표:
- 제출 전 로컬 검증(Strict)으로 형식 오류를 즉시 발견
- 벤치마크 대전 결과 + 패배 원인 요약 제공
- 다음 행동(서버 예측/최종 제출) 판단을 돕는 출력 제공

사용 예시:
    python student_package/local_test_runner.py student_package/agent_template.py
    python student_package/local_test_runner.py student_package/agent_template.py --show-final-board
    python student_package/local_test_runner.py student_package/agent_template.py --save-log local_result.json
    python student_package/local_test_runner.py --serve --port 59591
"""

import argparse
import importlib.util
import inspect
import json
import os
import sys
import tempfile
import time
import traceback
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from connect6.yukmok import YukmokState


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RUNNER_VERSION = "practice-local-runner/1.0"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 59591
DEFAULT_BENCHMARK_TIMEOUTS_MS = [100, 300, 500]
DEFAULT_BOARD_SIZE = 15
DEFAULT_WIN_STONES = 6

LOCAL_PRACTICE_OPPONENTS = {
    "starter": (
        "랜덤 기준 에이전트",
        os.path.join(THIS_DIR, "..", "reference_agents", "random_agent.py"),
    ),
}

REASON_LABELS = {
    "agent_exception": "agent exception",
    "timeout": "timeout",
    "invalid_return_type": "invalid return type",
    "invalid_return_length": "invalid return length",
    "invalid_move_type": "invalid move type",
    "non_integer_coordinate": "non-integer coordinate",
    "out_of_bounds": "out of bounds",
    "duplicate_move": "duplicate move in one turn",
    "occupied_position": "occupied position",
    "max_turns": "max turns",
}

TECHNICAL_REASON_CODES = {
    "agent_exception",
    "timeout",
    "invalid_return_type",
    "invalid_return_length",
    "invalid_move_type",
    "non_integer_coordinate",
    "out_of_bounds",
    "duplicate_move",
    "occupied_position",
}


def load_agent_module(path: str):
    spec = importlib.util.spec_from_file_location("student_agent", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "act"):
        raise RuntimeError("agent file must define `act(state, num_stones=2)`")
    return module


def validate_act_signature(agent_module) -> Tuple[bool, str]:
    try:
        sig = inspect.signature(agent_module.act)
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"cannot inspect act signature: {exc}"

    params = list(sig.parameters.values())
    if not params:
        return False, "act must accept at least one parameter: state"

    # 최소한 state를 받을 수 있어야 함
    if params[0].kind not in (
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ):
        return False, "first parameter must be positional `state`"

    # num_stones 파라미터 또는 가변 키워드 지원 확인
    has_num_stones = "num_stones" in sig.parameters
    has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
    if not has_num_stones and not has_var_kw:
        return False, "act must accept `num_stones` keyword argument"

    return True, "OK"


def strict_parse_moves(raw: Any, expected_count: int, board_size: int):
    """
    Strict 규약:
    - 반환형: list
    - 길이: expected_count (1 또는 2)
    - 원소: (row, col) 형태의 정수 2개
    - 중복 금지, 보드 범위 내
    """
    if not isinstance(raw, list):
        return None, "invalid_return_type", (
            f"Expected list[(row, col)] but received {type(raw).__name__}: {raw!r}"
        )

    if len(raw) != expected_count:
        return None, "invalid_return_length", (
            f"Expected {expected_count} moves but received {len(raw)}: {raw!r}"
        )

    seen = set()
    parsed: List[Tuple[int, int]] = []

    for idx, move in enumerate(raw, start=1):
        if not isinstance(move, (tuple, list)) or len(move) != 2:
            return None, "invalid_move_type", (
                f"Move #{idx} must be (row, col) pair, received: {move!r}"
            )

        row, col = move
        if not isinstance(row, int) or not isinstance(col, int):
            return None, "non_integer_coordinate", (
                f"Move #{idx} must use integer coordinates, received: {move!r}"
            )

        if row < 0 or col < 0 or row >= board_size or col >= board_size:
            return None, "out_of_bounds", (
                f"Move #{idx} out of bounds: {(row, col)} for board_size={board_size}"
            )

        key = (row, col)
        if key in seen:
            return None, "duplicate_move", (
                f"Duplicate move in one turn is not allowed: {(row, col)}"
            )
        seen.add(key)
        parsed.append(key)

    return parsed, None, None


def make_validation_state(stones_to_place: int) -> YukmokState:
    state = YukmokState(board_size=DEFAULT_BOARD_SIZE, win_stones=DEFAULT_WIN_STONES)
    state.stones_to_place = stones_to_place
    state.current_turn_placements = 0
    state.turn = 1
    return state


def run_preflight(agent_module) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "import_ok": True,
        "signature_ok": False,
        "signature_msg": "",
        "return_checks": [],
        "ok": False,
    }

    sig_ok, sig_msg = validate_act_signature(agent_module)
    report["signature_ok"] = sig_ok
    report["signature_msg"] = sig_msg
    if not sig_ok:
        return report

    checks = []
    for expected in (1, 2):
        state = make_validation_state(expected)
        try:
            raw = agent_module.act(state, num_stones=expected)
        except Exception:
            tb = traceback.format_exc(limit=5)
            checks.append({
                "num_stones": expected,
                "ok": False,
                "reason": "agent_exception",
                "message": "act() raised an exception during preflight",
                "traceback": tb,
            })
            report["return_checks"] = checks
            return report

        parsed, reason, detail = strict_parse_moves(raw, expected, state.board_size)
        if reason is not None:
            checks.append({
                "num_stones": expected,
                "ok": False,
                "reason": reason,
                "message": detail,
                "raw": repr(raw),
            })
            report["return_checks"] = checks
            return report

        checks.append({
            "num_stones": expected,
            "ok": True,
            "reason": None,
            "message": f"OK ({parsed})",
        })

    report["return_checks"] = checks
    report["ok"] = True
    return report


def board_to_ascii(state: YukmokState) -> str:
    symbols = {0: ".", 1: "X", -1: "O"}
    size = state.board_size
    lines = []

    header = "    " + " ".join(f"{c:02d}" for c in range(size))
    lines.append(header)
    for row in range(size):
        cells = []
        for col in range(size):
            val = int(state.game_board[row, col])
            cells.append(symbols.get(val, "?"))
        lines.append(f"{row:02d}  " + "  ".join(cells))

    return "\n".join(lines)


def one_game(black_agent, white_agent, timeout: float, max_turns: int, seed: Optional[int] = None):
    if seed is not None:
        random.seed(seed)
        try:
            import numpy as np
            np.random.seed(seed)
        except Exception:
            pass

    state = YukmokState(board_size=DEFAULT_BOARD_SIZE, win_stones=DEFAULT_WIN_STONES)
    turn = 0
    move_number = 0

    result: Dict[str, Any] = {
        "winner": None,          # 1 black / -1 white / 0 draw
        "reason_code": None,
        "reason_detail": "",
        "first_failure": None,
        "turns": 0,
        "moves": [],
        "traceback": None,
    }

    while turn < max_turns:
        current = black_agent if state.turn == 1 else white_agent
        player = state.turn
        player_name = "black" if player == 1 else "white"
        remaining = state.get_remaining_stones()

        start = time.time()
        try:
            raw = current.act(state, num_stones=remaining)
        except Exception:
            result["winner"] = -player
            result["reason_code"] = "agent_exception"
            result["reason_detail"] = f"{player_name} agent raised exception"
            result["traceback"] = traceback.format_exc(limit=5)
            result["first_failure"] = {
                "turn": turn + 1,
                "player": player_name,
                "num_stones": remaining,
                "reason": "agent_exception",
            }
            result["turns"] = turn
            return result, state

        elapsed = time.time() - start
        if elapsed > timeout:
            result["winner"] = -player
            result["reason_code"] = "timeout"
            result["reason_detail"] = (
                f"{player_name} timeout ({elapsed:.3f}s > {timeout:.3f}s)"
            )
            result["first_failure"] = {
                "turn": turn + 1,
                "player": player_name,
                "num_stones": remaining,
                "reason": "timeout",
                "elapsed": round(elapsed, 4),
            }
            result["turns"] = turn
            return result, state

        moves, reason, detail = strict_parse_moves(raw, remaining, state.board_size)
        if reason is not None:
            result["winner"] = -player
            result["reason_code"] = reason
            result["reason_detail"] = f"{player_name}: {detail}"
            result["first_failure"] = {
                "turn": turn + 1,
                "player": player_name,
                "num_stones": remaining,
                "reason": reason,
                "detail": detail,
            }
            result["turns"] = turn
            return result, state

        assert moves is not None
        for row, col in moves:
            if not state.is_valid_position(col, row):
                result["winner"] = -player
                result["reason_code"] = "occupied_position"
                result["reason_detail"] = (
                    f"{player_name} tried occupied position: {(row, col)}"
                )
                result["first_failure"] = {
                    "turn": turn + 1,
                    "player": player_name,
                    "num_stones": remaining,
                    "reason": "occupied_position",
                    "move": (row, col),
                }
                result["turns"] = turn
                return result, state

            state.update(col, row)
            move_number += 1
            result["moves"].append({
                "move_number": move_number,
                "turn": turn + 1,
                "player": player_name,
                "move": (row, col),
                "response_ms": round(elapsed * 1000.0, 3),
            })

            status = state.check_status()
            if status is not None:
                if status == 1:
                    result["winner"] = 1
                elif status == 2:
                    result["winner"] = -1
                else:
                    result["winner"] = 0
                result["reason_code"] = "game_end"
                result["reason_detail"] = "normal game end"
                result["turns"] = turn + 1
                return result, state

        turn += 1

    result["winner"] = 0
    result["reason_code"] = "max_turns"
    result["reason_detail"] = f"draw by max_turns={max_turns}"
    result["turns"] = turn
    return result, state


def run_series(
    candidate_path: str,
    opponent_path: str,
    games: int,
    timeout: float,
    max_turns: int,
    seed: Optional[int] = None,
):
    candidate = load_agent_module(candidate_path)
    opponent = load_agent_module(opponent_path)

    wins = 0
    losses = 0
    draws = 0

    loss_reasons: Dict[str, int] = {}
    first_failure: Optional[Dict[str, Any]] = None
    first_failure_traceback: Optional[str] = None
    last_losing_state_ascii: Optional[str] = None

    game_logs: List[Dict[str, Any]] = []

    for i in range(games):
        game_seed = None if seed is None else seed + i
        if i % 2 == 0:
            game_result, final_state = one_game(candidate, opponent, timeout, max_turns, seed=game_seed)
            candidate_color = "black"
            candidate_is_black = True
        else:
            game_result, final_state = one_game(opponent, candidate, timeout, max_turns, seed=game_seed)
            candidate_color = "white"
            candidate_is_black = False

        winner = game_result["winner"]
        if winner == 0:
            outcome = "draw"
            draws += 1
        elif (winner == 1 and candidate_is_black) or (winner == -1 and not candidate_is_black):
            outcome = "win"
            wins += 1
        else:
            outcome = "loss"
            losses += 1

            reason_code = game_result.get("reason_code") or "unknown"
            loss_reasons[reason_code] = loss_reasons.get(reason_code, 0) + 1
            if first_failure is None:
                first_failure = {
                    "game_index": i + 1,
                    "candidate_color": candidate_color,
                    "reason_code": reason_code,
                    "reason_label": REASON_LABELS.get(reason_code, reason_code),
                    "reason_detail": game_result.get("reason_detail", ""),
                    "failure": game_result.get("first_failure"),
                }
                first_failure_traceback = game_result.get("traceback")
            last_losing_state_ascii = board_to_ascii(final_state)

        game_logs.append({
            "game_index": i + 1,
            "candidate_color": candidate_color,
            "outcome": outcome,
            "winner": winner,
            "reason_code": game_result.get("reason_code"),
            "reason_detail": game_result.get("reason_detail"),
            "first_failure": game_result.get("first_failure"),
            "traceback": game_result.get("traceback"),
            "turns": game_result.get("turns"),
            "moves": game_result.get("moves") or [],
        })

    score = (wins + 0.5 * draws) / games if games > 0 else 0.0
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score": score,
        "loss_reasons": loss_reasons,
        "first_failure": first_failure,
        "first_failure_traceback": first_failure_traceback,
        "last_losing_state_ascii": last_losing_state_ascii,
        "games": game_logs,
    }


def summarize_actions(avg_score: float, total_technical_failures: int) -> Tuple[str, List[str]]:
    if total_technical_failures > 0:
        return "검증 실패", [
            "반환 형식을 list[(row, col)]로 고정하세요.",
            "num_stones=1이면 길이 1, num_stones=2이면 길이 2를 반환하세요.",
            "에러/타임아웃 로그를 먼저 제거한 뒤 다시 벤치마크를 실행하세요.",
        ]

    if avg_score >= 0.60:
        return "제출 준비", [
            "현재 로컬 성능은 제출 가능한 수준입니다.",
            "서버 예측 단계(/predict)에서 재검증 후 최종 제출하세요.",
        ]

    if avg_score >= 0.35:
        return "예측 가능", [
            "서버 예측은 가능하지만 Baseline 대응 개선을 권장합니다.",
            "수비 휴리스틱(상대 4~5목 차단) 우선순위를 높여보세요.",
        ]

    return "개선 필요", [
        "공격/수비 평가 함수를 강화하고 중앙 편향을 완화해보세요.",
        "상대 위협 차단(즉시 패배 수) 규칙을 먼저 구현하세요.",
        "로컬 검증 통과 후 서버 예측 단계로 이동하세요.",
    ]


def maybe_save_log(path: Optional[str], payload: Dict[str, Any]) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _preflight_error_message(preflight: Dict[str, Any]) -> str:
    if not preflight.get("signature_ok"):
        return str(preflight.get("signature_msg") or "act 시그니처 검증 실패")
    for row in preflight.get("return_checks") or []:
        if not row.get("ok"):
            return str(row.get("message") or row.get("reason") or "반환 형식 검증 실패")
    return "로컬 사전 검증 실패"


def _normalize_moves_for_submission(raw_moves: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_moves, list):
        return []

    moves: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw_moves, start=1):
        row: Optional[int] = None
        col: Optional[int] = None
        player = "black" if idx % 2 == 1 else "white"
        move_number = idx

        if isinstance(item, dict):
            player_raw = str(item.get("player") or "").strip().lower()
            if player_raw in {"black", "white"}:
                player = player_raw
            if item.get("move_number") is not None:
                try:
                    move_number = int(item.get("move_number"))
                except Exception:
                    move_number = idx
            pair = item.get("move")
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                try:
                    row = int(pair[0])
                    col = int(pair[1])
                except Exception:
                    row = None
                    col = None
            if row is None or col is None:
                try:
                    row = int(item.get("row"))
                    col = int(item.get("col"))
                except Exception:
                    row = None
                    col = None
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            try:
                row = int(item[0])
                col = int(item[1])
            except Exception:
                row = None
                col = None

        if row is None or col is None:
            continue

        moves.append({
            "move_number": move_number,
            "player": player,
            "row": row,
            "col": col,
        })

    return moves


def _sanitize_timeout_limits(values: Any) -> List[int]:
    if not isinstance(values, list):
        return list(DEFAULT_BENCHMARK_TIMEOUTS_MS)
    out: List[int] = []
    for raw in values:
        try:
            value = int(raw)
        except Exception:
            continue
        if value < 50 or value > 5000:
            continue
        if value not in out:
            out.append(value)
    return out or list(DEFAULT_BENCHMARK_TIMEOUTS_MS)


def _series_to_practice_profile(
    series: Dict[str, Any],
    *,
    time_limit_ms: Optional[int],
    timeout_label: str,
    game_index_offset: int,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    raw_games = series.get("games") or []
    game_logs: List[Dict[str, Any]] = []

    total_turns = 0
    max_response_ms = 0.0
    for index, row in enumerate(raw_games, start=1):
        game = row if isinstance(row, dict) else {}
        turns = int(game.get("turns") or 0)
        total_turns += turns
        candidate_player = str(game.get("candidate_color") or "").strip().lower()
        game_candidate_max_ms = 0.0
        for move in game.get("moves") or []:
            if not isinstance(move, dict):
                continue
            if str(move.get("player") or "").strip().lower() != candidate_player:
                continue
            try:
                game_candidate_max_ms = max(game_candidate_max_ms, float(move.get("response_ms") or 0.0))
            except Exception:
                pass
        max_response_ms = max(max_response_ms, game_candidate_max_ms)
        reason_code = str(game.get("reason_code") or "").strip()
        reason_detail = str(game.get("reason_detail") or "").strip()
        termination_reason = reason_detail or REASON_LABELS.get(reason_code, reason_code or "-")

        game_logs.append({
            "game_index": game_index_offset + index,
            "time_limit_ms": time_limit_ms,
            "timeout_label": timeout_label,
            "candidate_color": game.get("candidate_color") or "-",
            "outcome": game.get("outcome") or "-",
            "termination_reason": termination_reason or "-",
            "total_turns": turns,
            "max_candidate_response_ms": round(game_candidate_max_ms, 3),
            "moves": _normalize_moves_for_submission(game.get("moves")),
        })

    game_count = len(game_logs)
    avg_turns = round((total_turns / game_count), 2) if game_count > 0 else 0.0
    profile = {
        "time_limit_ms": time_limit_ms,
        "wins": int(series.get("wins") or 0),
        "losses": int(series.get("losses") or 0),
        "draws": int(series.get("draws") or 0),
        "avg_turns": avg_turns,
        "max_response_time_ms": round(max_response_ms, 3),
    }
    return profile, game_logs


def _build_single_timeout_summary(
    candidate_path: str,
    *,
    opponent_key: str,
    games: int,
    max_turns: int,
    seed: Optional[int] = None,
    time_limit_ms: int = 5000,
) -> Dict[str, Any]:
    opponent_name, opponent_path = LOCAL_PRACTICE_OPPONENTS[opponent_key]
    series = run_series(
        candidate_path,
        opponent_path,
        games,
        max(0.05, float(time_limit_ms) / 1000.0),
        max_turns,
        seed=seed,
    )
    profile, game_logs = _series_to_practice_profile(
        series,
        time_limit_ms=time_limit_ms,
        timeout_label=f"{time_limit_ms}ms",
        game_index_offset=0,
    )

    return {
        "mode": "single_timeout",
        "opponent_key": opponent_key,
        "opponent_name": opponent_name,
        "games": len(game_logs),
        "wins": profile["wins"],
        "losses": profile["losses"],
        "draws": profile["draws"],
        "avg_turns": profile["avg_turns"],
        "max_response_time_ms": profile["max_response_time_ms"],
        "timeout_profiles": [],
        "benchmark_note": "",
        "game_logs": game_logs,
    }


def _build_timeout_benchmark_summary(
    candidate_path: str,
    *,
    opponent_key: str,
    games: int,
    max_turns: int,
    timeout_limits_ms: List[int],
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    opponent_name, opponent_path = LOCAL_PRACTICE_OPPONENTS[opponent_key]
    profiles: List[Dict[str, Any]] = []
    all_logs: List[Dict[str, Any]] = []

    for timeout_ms in timeout_limits_ms:
        series = run_series(
            candidate_path,
            opponent_path,
            games,
            max(0.05, float(timeout_ms) / 1000.0),
            max_turns,
            seed=seed,
        )
        profile, logs = _series_to_practice_profile(
            series,
            time_limit_ms=timeout_ms,
            timeout_label=f"{timeout_ms}ms",
            game_index_offset=len(all_logs),
        )
        profiles.append(profile)
        all_logs.extend(logs)

    total_games = len(all_logs)
    wins = sum(int(x.get("wins") or 0) for x in profiles)
    losses = sum(int(x.get("losses") or 0) for x in profiles)
    draws = sum(int(x.get("draws") or 0) for x in profiles)
    weighted_turns = 0.0
    for profile in profiles:
        profile_games = int(profile.get("wins") or 0) + int(profile.get("losses") or 0) + int(profile.get("draws") or 0)
        weighted_turns += float(profile.get("avg_turns") or 0.0) * profile_games
    avg_turns = round((weighted_turns / total_games), 2) if total_games > 0 else 0.0
    max_response_time_ms = max((float(x.get("max_response_time_ms") or 0.0) for x in profiles), default=0.0)

    return {
        "mode": "timeout_benchmark",
        "opponent_key": opponent_key,
        "opponent_name": opponent_name,
        "games": total_games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "avg_turns": avg_turns,
        "max_response_time_ms": round(max_response_time_ms, 3),
        "timeout_profiles": profiles,
        "benchmark_note": f"시간 제한 {', '.join(str(x) for x in timeout_limits_ms)}ms 실행",
        "game_logs": all_logs,
    }


def run_practice_submission(
    *,
    code: str,
    opponent_key: str,
    games: int,
    timeout_benchmark: bool,
    timeout_limits_ms: List[int],
    max_turns: int,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            candidate_module = load_agent_module(temp_path)
        except Exception as exc:
            return {"success": False, "error": f"코드 로드 실패: {exc}"}

        preflight = run_preflight(candidate_module)
        if not preflight.get("ok"):
            return {
                "success": False,
                "error": _preflight_error_message(preflight),
                "preflight": preflight,
            }

        if opponent_key not in LOCAL_PRACTICE_OPPONENTS:
            return {"success": False, "error": "지원하지 않는 기준 에이전트입니다."}

        if timeout_benchmark:
            summary = _build_timeout_benchmark_summary(
                temp_path,
                opponent_key=opponent_key,
                games=games,
                max_turns=max_turns,
                timeout_limits_ms=timeout_limits_ms,
                seed=seed,
            )
        else:
            summary = _build_single_timeout_summary(
                temp_path,
                opponent_key=opponent_key,
                games=games,
                max_turns=max_turns,
                seed=seed,
            )

        return {
            "success": True,
            "runner_version": RUNNER_VERSION,
            "summary": summary,
        }
    except Exception as exc:
        return {"success": False, "error": f"로컬 실행 중 오류: {exc}"}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def serve_local_runner(host: str, port: int) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class RunnerHandler(BaseHTTPRequestHandler):
        server_version = "PracticeLocalRunnerHTTP/1.0"

        def _set_common_headers(self, *, content_type: str = "application/json; charset=utf-8") -> None:
            self.send_header("Content-Type", content_type)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _write_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self._set_common_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._set_common_headers()
            self.end_headers()

        def do_GET(self) -> None:
            if self.path != "/health":
                self._write_json(404, {"success": False, "error": "not found"})
                return
            self._write_json(200, {
                "success": True,
                "status": "ok",
                "runner_version": RUNNER_VERSION,
                "supported_opponents": list(LOCAL_PRACTICE_OPPONENTS.keys()),
            })

        def do_POST(self) -> None:
            if self.path != "/run":
                self._write_json(404, {"success": False, "error": "not found"})
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(max(0, length)).decode("utf-8") if length > 0 else "{}"
                payload = json.loads(raw) if raw.strip() else {}
                if not isinstance(payload, dict):
                    raise ValueError("요청 본문은 JSON 객체여야 합니다.")
            except Exception as exc:
                self._write_json(400, {"success": False, "error": f"잘못된 요청 본문: {exc}"})
                return

            code = str(payload.get("code") or "")
            if not code.strip():
                self._write_json(400, {"success": False, "error": "코드가 비어 있습니다."})
                return

            opponent_key = str(payload.get("opponent_key") or "starter").strip().lower()
            if opponent_key not in LOCAL_PRACTICE_OPPONENTS:
                self._write_json(400, {"success": False, "error": "지원하지 않는 기준 에이전트입니다."})
                return

            try:
                games = int(payload.get("games", 6))
            except Exception:
                games = 6
            games = max(1, min(games, 200))

            try:
                max_turns = int(payload.get("max_turns", 300))
            except Exception:
                max_turns = 300
            max_turns = max(50, min(max_turns, 2000))

            timeout_benchmark = bool(payload.get("timeout_benchmark"))
            timeout_limits_ms = _sanitize_timeout_limits(payload.get("timeout_limits_ms"))

            seed_raw = payload.get("seed")
            seed: Optional[int] = None
            if seed_raw is not None:
                try:
                    seed = int(seed_raw)
                except Exception:
                    seed = None

            result = run_practice_submission(
                code=code,
                opponent_key=opponent_key,
                games=games,
                timeout_benchmark=timeout_benchmark,
                timeout_limits_ms=timeout_limits_ms,
                max_turns=max_turns,
                seed=seed,
            )
            if not result.get("success"):
                self._write_json(400, result)
                return
            self._write_json(200, result)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer((host, port), RunnerHandler)
    print(f"[local-runner] listening on http://{host}:{port}")
    print(f"[local-runner] version={RUNNER_VERSION}")
    print(f"[local-runner] opponents={', '.join(LOCAL_PRACTICE_OPPONENTS.keys())}")
    server.serve_forever()


def print_preflight(preflight: Dict[str, Any]) -> None:
    print("=== Step 1. 로컬 검증 (Strict) ===")
    print("Import: OK")
    print(f"act signature: {'OK' if preflight['signature_ok'] else 'FAIL'}")
    if not preflight["signature_ok"]:
        print(f"- {preflight['signature_msg']}")
        return

    for chk in preflight["return_checks"]:
        tag = "OK" if chk["ok"] else "FAIL"
        print(f"Return format (num_stones={chk['num_stones']}): {tag}")
        if not chk["ok"]:
            print(f"- reason: {chk['reason']}")
            print(f"- detail: {chk['message']}")
            if chk.get("traceback"):
                print("- traceback (top 5 lines):")
                for line in chk["traceback"].strip().splitlines()[:5]:
                    print(f"  {line}")


def print_reason_summary(reason_counts: Dict[str, int]) -> None:
    if not reason_counts:
        print("  - none")
        return
    for code, count in sorted(reason_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {REASON_LABELS.get(code, code)}: {count}")


def main():
    if "--serve" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--serve", action="store_true")
        parser.add_argument("--host", type=str, default=DEFAULT_HTTP_HOST)
        parser.add_argument("--port", type=int, default=DEFAULT_HTTP_PORT)
        args = parser.parse_args()
        serve_local_runner(args.host, args.port)
        return

    parser = argparse.ArgumentParser()
    parser.add_argument("agent", help="path to your agent file")
    parser.add_argument("--games", type=int, default=8, help="games vs local reference agent")
    parser.add_argument("--timeout", type=float, default=5.0, help="seconds per move")
    parser.add_argument("--max-turns", type=int, default=300, help="turn cap")
    parser.add_argument("--seed", type=int, default=None, help="fixed seed for reproducible local tests")
    parser.add_argument("--show-final-board", action="store_true", help="show final board of first losing game")
    parser.add_argument("--save-log", type=str, default=None, help="save JSON report path")
    parser.add_argument("--validate-only", action="store_true", help="run strict interface preflight only")
    args = parser.parse_args()

    candidate_path = args.agent
    if not os.path.isabs(candidate_path):
        candidate_path = os.path.normpath(os.path.join(os.getcwd(), candidate_path))

    if not os.path.exists(candidate_path):
        raise SystemExit(f"agent file not found: {candidate_path}")

    print("=== 육목(connect-6) Local Validation Runner ===")
    print(f"agent: {candidate_path}")
    print(f"games per local reference: {args.games}")
    print(f"timeout per move: {args.timeout:.2f}s")
    print(f"max turns: {args.max_turns}")
    if args.seed is not None:
        print(f"seed: {args.seed}")
    print()

    # 1) Preflight (strict)
    try:
        candidate_module = load_agent_module(candidate_path)
    except Exception as exc:
        print("=== Step 1. 로컬 검증 (Strict) ===")
        print("Import: FAIL")
        print(f"- {exc}")
        raise SystemExit(1)

    preflight = run_preflight(candidate_module)
    print_preflight(preflight)
    if not preflight.get("ok"):
        print()
        print("검증 실패: 벤치마크 실행을 중단합니다.")
        print("Fix guide:")
        print("- act(state, num_stones=2)를 구현하세요.")
        print("- 반환 형식은 항상 list[(row, col)] 이어야 합니다.")
        print("- num_stones=1 => 길이 1, num_stones=2 => 길이 2")
        raise SystemExit(1)
    if args.validate_only:
        print()
        print("검증 통과: --validate-only 옵션으로 벤치마크는 생략합니다.")
        raise SystemExit(0)

    print()
    print("=== Step 2. 벤치마크 대전 ===")

    reference_agents = [
        ("Random", os.path.join(THIS_DIR, "..", "reference_agents", "random_agent.py")),
    ]

    total_score = 0.0
    valid_reference_agents = 0
    all_reason_counts: Dict[str, int] = {}
    first_global_failure: Optional[Dict[str, Any]] = None
    first_global_traceback: Optional[str] = None
    first_losing_board: Optional[str] = None

    benchmark_results = []

    for name, path in reference_agents:
        if not os.path.exists(path):
            continue

        summary = run_series(
            candidate_path, path, args.games, args.timeout, args.max_turns, seed=args.seed
        )
        wins = summary["wins"]
        losses = summary["losses"]
        draws = summary["draws"]
        score = summary["score"]

        total_score += score
        valid_reference_agents += 1

        print(f"[{name:8s}] {wins}W-{losses}L-{draws}D | score={score:.3f}")
        print("- Loss reasons:")
        print_reason_summary(summary["loss_reasons"])

        for code, count in summary["loss_reasons"].items():
            all_reason_counts[code] = all_reason_counts.get(code, 0) + count

        if first_global_failure is None and summary["first_failure"] is not None:
            first_global_failure = {"benchmark": name, **summary["first_failure"]}
            first_global_traceback = summary.get("first_failure_traceback")
            first_losing_board = summary.get("last_losing_state_ascii")

        benchmark_results.append({"name": name, **summary})
        print()

    if valid_reference_agents == 0:
        print("No local reference agents available.")
        raise SystemExit(1)

    avg_score = total_score / valid_reference_agents
    total_technical_failures = sum(
        count for code, count in all_reason_counts.items()
        if code in TECHNICAL_REASON_CODES
    )

    print("=== Step 3. 종합 해석 ===")
    print(f"Average score: {avg_score:.3f}")

    status, actions = summarize_actions(avg_score, total_technical_failures)
    print(f"Status: {status}")

    if first_global_failure:
        print("First failure:")
        print(
            f"- benchmark={first_global_failure['benchmark']}, "
            f"game={first_global_failure['game_index']}, "
            f"color={first_global_failure['candidate_color']}, "
            f"reason={first_global_failure['reason_label']}"
        )
        detail = first_global_failure.get("reason_detail")
        if detail:
            print(f"- detail: {detail}")

        if first_global_traceback:
            print("- traceback (top 5 lines):")
            for line in first_global_traceback.strip().splitlines()[:5]:
                print(f"  {line}")

    print("Next actions:")
    for action in actions:
        print(f"- {action}")

    print("Flow:")
    print("1) 로컬 직접 대국(play_local.py)으로 AI 행동 확인")
    print("2) 로컬 strict 검증 + 랜덤 기준 AI 벤치마크")
    print("3) 웹 연습 대국(/test)에서 서버 실행 결과 확인")
    print("4) 최종 제출/결과 확인(/upload) 및 리더보드 확인")

    if args.show_final_board and first_losing_board:
        print()
        print("=== Final Board (first losing game) ===")
        print(first_losing_board)

    log_payload = {
        "timestamp": datetime.now().isoformat(),
        "agent": candidate_path,
        "settings": {
            "games": args.games,
            "timeout": args.timeout,
            "max_turns": args.max_turns,
            "seed": args.seed,
        },
        "preflight": preflight,
        "benchmarks": benchmark_results,
        "summary": {
            "avg_score": avg_score,
            "status": status,
            "reason_counts": all_reason_counts,
            "first_failure": first_global_failure,
        },
    }
    maybe_save_log(args.save_log, log_payload)
    if args.save_log:
        print(f"Saved log: {args.save_log}")


if __name__ == "__main__":
    main()
