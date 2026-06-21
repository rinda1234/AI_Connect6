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
    # 중복 제거를 위해 set 사용
    candidates = set()

    # 기존 돌 주변 2칸 이내 후보를 생성
    for row in range(state.board_size):
        for col in range(state.board_size):
            # 기존 돌이 있는지 확인
            if state.game_board[row][col] != 0:
  
                # 주변 2칸 이내 후보를 생성
                for target_row in range(-2 + row, 3 + row):
                    for target_col in range(-2 + col, 3 + col):
                        # 기존 돌이 있는 위치는 후보에서 제외
                        if (target_row, target_col) not in blocked:
                            # 유효한 위치인지 확인 후 후보에 추가
                            if state.is_valid_position(target_col, target_row):
                                candidates.add((target_row, target_col))
                      
    return list(candidates)

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
    row, col = move

    target_Player = 2 if player == 1 else 1

        # 방향
    directions = [
        (0, 1),    # 가로
        (1, 0),    # 세로
        (1, 1),    # ↘ 대각선
        (1, -1)    # ↗ 대각선
    ]

    # 패턴 점수표
    pattern_score = {
        "111111": 10000000,

        "0111110": 1000000, 
        "2111110": 500000,
        "0111112": 500000,

        "011110": 50000,
        "211110": 10000,
        "011112": 10000,

        "01110": 3000,
        "21110": 500,
        "01112": 500,

        "0110": 100,
        "010": 10
    }

    # 공격 평가
    state.game_board[row, col] = player
    # 4방향에 대해 패턴 매칭을 통해 점수 계산
    total_attack = 0
    for dr, dc in directions:
        # 각 방향에 대해 현재 위치 포함 양쪽으로 6칸 문자열 생성
        target_line = ""

        for k in range(-6, 7):
            #     
            target_row = row + dr * k
            target_col = col + dc * k

            # 보드 범위 밖은 상대 돌로 간주
            if ((0 > target_row or target_row >= state.board_size) or 
                (0 > target_col or target_col >= state.board_size)):
                target_line += "2"
            elif state.game_board[target_row, target_col] == 0:
                target_line += "0"
            elif state.game_board[target_row, target_col] == player:
                target_line += "1"
            else:
                target_line += "2"

        for pattern, score in pattern_score.items():

            if pattern in target_line:
                total_attack += score

    state.game_board[row, col] = 0

    # 수비 평가
    total_defense = 0
    for dr, dc in directions:
        target_line = ""

        for k in range(-6, 7):
            target_row = row + dr * k
            target_col = col + dc * k

            if ((0 > target_row or target_row >= state.board_size) or 
                (0 > target_col or target_col >= state.board_size)):
                target_line += "2"
            elif state.game_board[target_row, target_col] == 0:
                target_line += "0"
            elif state.game_board[target_row, target_col] == target_Player:
                target_line += "1"
            else:
                target_line += "2"

    # 패턴 매칭을 통해 점수 계산
        for pattern, score in pattern_score.items():
            if pattern in target_line:
                total_defense += score

    state.game_board[row, col] = 0

    # 가장자리 기피, 중앙 선호를 위한 거리 기반 점수 계산
    center_score = state.board_size - (abs(row - state.board_size // 2) + abs(col - state.board_size // 2))
    
    return total_attack + int(total_defense * 1.5)  + center_score


def choose_one_move(state, player: int, blocked: Set[Move]) -> Move:
    """
    TODO:
    여기에 rule-based / minimax / alpha-beta / 휴리스틱 등을 구현하세요.
    아래 구현은 후보 중 평가 점수가 가장 높은 좌표를 고르는 가장 단순한 뼈대입니다.
    """
    target_Player = 2 if player == 1 else 1
    # 후보 생성
    candidates = generate_candidates(state, player, blocked)
    if not candidates:
        return (state.board_size // 2, state.board_size // 2)
    
    # 후보 축소
    candidates = sorted(candidates, key=lambda move: evaluate_move(state, player, move), reverse=True)[:10]

    # minimax / alpha-beta / 휴리스틱 등을 통해 후보 중 하나를 선택
    def minimax(depth, alpha, beta, maximizing, current_player):

        # 종료 조건
        if depth == 0:
            return evaluate_move(state, player, (0, 0))  
        # 현재 플레이어가 둘 수 있는 후보 수를 생성
        moves = generate_candidates(state, current_player, set())
        if not moves:
            return 0

        # 후보 수 정렬 상위 6개만 선택
        moves = sorted(
            moves,
            key=lambda m: evaluate_move(state, current_player, m),
            reverse=True
        )[:6]

        # 내 턴
        if maximizing:
            # 최대값 초기화
            value = -float("inf")

            for r, c in moves:
                state.game_board[r, c] = current_player

                # 재귀 호출로 상대 턴으로 전환해서 한 단계 내려감
                value = max(
                    value,
                    minimax(
                        depth - 1,
                        alpha,
                        beta,
                        False,
                        target_Player if current_player == player else player
                    )
                )
                # 보드 원상 복구
                state.game_board[r, c] = 0

                # alpha 업데이트
                alpha = max(alpha, value)
                # 가지치기
                if beta <= alpha:
                    break

            return value
        # 상대 턴
        else:
            value = float("inf")

            for r, c in moves:
                state.game_board[r, c] = current_player

                value = min(
                    value,
                    minimax(
                        depth - 1,
                        alpha,
                        beta,
                        True,
                        target_Player if current_player == player else player
                    )
                )

                state.game_board[r, c] = 0

                beta = min(beta, value)
                if beta <= alpha:
                    break

            return value

    # 실제 선택 -> 최댓값 move 선택
    best_move = candidates[0]
    best_score = -float("inf")

    for r, c in candidates:

        state.game_board[r, c] = player
        # minimax를 통해 상대방의 최적 대응을 고려한 점수 계산
        score = minimax(
            2,  # depth
            -float("inf"),
            float("inf"),
            False,
            target_Player   
        )

        state.game_board[r, c] = 0
        # 최대 점수 갱신
        if score > best_score:
            best_score = score
            best_move = (r, c)

    return best_move



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
    # 현재 차레인 플레이어
    player = state.turn
    # 이번 턴에 실제로 둘 수 있는 돌 개수 계산
    remaining = min(num_stones, state.get_remaining_stones())
    # 결과 저장용
    moves: List[Move] = []
    # 중복 방지용
    used: Set[Move] = set()
    # 돌 개수만큼 반복하여 선택
    for _ in range(remaining):
        # 현재 상태에서 가장 좋은 한 수 선택
        move = choose_one_move(state, player, used)
        moves.append(move)
        used.add(move)

    return moves
