"""
랜덤 Agent (Strict 규약 버전)

반환 규약:
- 항상 list[(row, col)]
- num_stones=1이면 길이 1, num_stones=2이면 길이 2
"""

import numpy as np


def act(state, num_stones=2):
    remaining = min(num_stones, state.get_remaining_stones())
    board_size = state.board_size
    moves = []
    used = set()

    for _ in range(remaining):
        placed = False

        # 랜덤 탐색
        for _ in range(1000):
            row = int(np.random.randint(0, board_size))
            col = int(np.random.randint(0, board_size))
            if (row, col) in used:
                continue
            if state.is_valid_position(col, row):
                moves.append((row, col))
                used.add((row, col))
                placed = True
                break

        # fallback: 첫 번째 유효 위치
        if not placed:
            for row in range(board_size):
                for col in range(board_size):
                    if (row, col) in used:
                        continue
                    if state.is_valid_position(col, row):
                        moves.append((row, col))
                        used.add((row, col))
                        placed = True
                        break
                if placed:
                    break

    return moves
