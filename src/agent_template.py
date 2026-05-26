"""
육목(connect-6) 과제용 학생 템플릿

필수 구현:
- act(state, num_stones=2) -> list[(row, col)]

중요 규약 (Strict):
- 반환형은 항상 list
- num_stones=1이면 길이 1, num_stones=2이면 길이 2
- 좌표 형식은 (row, col)
"""

from typing import List, Set, Tuple

Move = Tuple[int, int]  # (row, col)


def iter_valid_moves(state, blocked: Set[Move] | None = None) -> List[Move]:
    """현재 보드에서 둘 수 있는 모든 좌표를 (row, col) 형식으로 반환합니다."""
    blocked = blocked or set()
    moves: List[Move] = []
    for row in range(state.board_size):
        for col in range(state.board_size):
            if (row, col) in blocked:
                continue
            if state.is_valid_position(col, row):
                moves.append((row, col))
    return moves


def generate_candidates(state, player: int, blocked: Set[Move]) -> List[Move]:
    """
    TODO:
    모든 빈 칸을 그대로 반환하면 동작은 하지만 느리고 약할 수 있습니다.
    기존 돌 주변, 중앙 근처, 공격/수비 가치가 높은 위치만 남기는 방식으로
    후보 수를 줄여 보세요.
    """
    _ = player
    return iter_valid_moves(state, blocked)


def evaluate_move(state, player: int, move: Move) -> int:
    """
    TODO:
    move를 두었을 때의 가치를 점수로 계산해 보세요.
    예시로 고려할 수 있는 요소:
    - 내 돌이 연속으로 이어지는 길이
    - 상대의 위협을 막는지 여부
    - 열린 방향 수
    - 중앙 또는 기존 돌과의 거리
    """
    _ = state
    _ = player
    _ = move
    return 0


def choose_one_move(state, player: int, blocked: Set[Move]) -> Move:
    """
    TODO:
    여기에 rule-based / minimax / alpha-beta / 휴리스틱 등을 구현하세요.
    아래 구현은 후보 중 평가 점수가 가장 높은 좌표를 고르는 가장 단순한 뼈대입니다.
    """
    candidates = generate_candidates(state, player, blocked)
    if candidates:
        return max(candidates, key=lambda move: evaluate_move(state, player, move))

    # 보드가 가득 찬 예외 상황 fallback
    return (state.board_size // 2, state.board_size // 2)


def act(state, num_stones=2) -> List[Move]:
    """
    Args:
        state: YukmokState
        num_stones: 이번 호출에서 놓을 돌 개수 (1 또는 2)

    Returns:
        list[(row, col)]
        - num_stones=1: 길이 1
        - num_stones=2: 길이 2
    """
    player = state.turn
    remaining = min(num_stones, state.get_remaining_stones())

    moves: List[Move] = []
    used: Set[Move] = set()
    for _ in range(remaining):
        move = choose_one_move(state, player, used)
        moves.append(move)
        used.add(move)

    return moves
