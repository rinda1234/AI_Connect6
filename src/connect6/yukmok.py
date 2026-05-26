import numpy as np


class YukmokState:
    """
    육목(connect-6) game state.

    Board encoding:
    - 0: empty
    - 1: black
    - -1: white
    """

    def __init__(self, game_board=None, board_size=15, win_stones=6):
        self.game_board = game_board if game_board is not None else np.zeros(
            [board_size, board_size]
        )
        self.board_size = board_size
        self.win_stones = win_stones
        self.num_stones = 0
        self.history = []
        self.turn = 1  # black: 1, white: -1
        self.stones_to_place = 1  # first black turn: one stone
        self.current_turn_placements = 0

    def reset(self):
        self.game_board = np.zeros([self.board_size, self.board_size])
        self.num_stones = 0
        self.history = []
        self.turn = 1
        self.stones_to_place = 1
        self.current_turn_placements = 0

    def clone(self):
        """현재 상태를 깊은 복사해 시뮬레이션에 사용."""
        copied = YukmokState(
            game_board=np.array(self.game_board, copy=True),
            board_size=self.board_size,
            win_stones=self.win_stones,
        )
        copied.num_stones = self.num_stones
        copied.history = list(self.history)
        copied.turn = self.turn
        copied.stones_to_place = self.stones_to_place
        copied.current_turn_placements = self.current_turn_placements
        return copied

    def check_status(self):
        """Returns: 1 (black win), 2 (white win), 3 (draw), or None."""
        if self.num_stones == self.board_size * self.board_size:
            return 3

        # Horizontal
        for row in range(self.board_size):
            for col in range(self.board_size - self.win_stones + 1):
                segment_sum = np.sum(self.game_board[row, col : col + self.win_stones])
                if segment_sum == self.win_stones:
                    return 1
                if segment_sum == -self.win_stones:
                    return 2

        # Vertical
        for row in range(self.board_size - self.win_stones + 1):
            for col in range(self.board_size):
                segment_sum = np.sum(self.game_board[row : row + self.win_stones, col])
                if segment_sum == self.win_stones:
                    return 1
                if segment_sum == -self.win_stones:
                    return 2

        # Main diagonal
        for row in range(self.board_size - self.win_stones + 1):
            for col in range(self.board_size - self.win_stones + 1):
                count_sum = 0
                for i in range(self.win_stones):
                    if self.game_board[row + i, col + i] == 1:
                        count_sum += 1
                    if self.game_board[row + i, col + i] == -1:
                        count_sum -= 1
                if count_sum == self.win_stones:
                    return 1
                if count_sum == -self.win_stones:
                    return 2

        # Anti-diagonal
        for row in range(self.win_stones - 1, self.board_size):
            for col in range(self.board_size - self.win_stones + 1):
                count_sum = 0
                for i in range(self.win_stones):
                    if self.game_board[row - i, col + i] == 1:
                        count_sum += 1
                    if self.game_board[row - i, col + i] == -1:
                        count_sum -= 1
                if count_sum == self.win_stones:
                    return 1
                if count_sum == -self.win_stones:
                    return 2

        return None

    def is_valid_position(self, x_pos, y_pos):
        if x_pos < 0 or y_pos < 0 or x_pos >= self.board_size or y_pos >= self.board_size:
            return False
        return self.game_board[y_pos, x_pos] == 0

    def update(self, x_pos, y_pos):
        self.game_board[y_pos, x_pos] = 1 if self.turn == 1 else -1
        self.history.append((x_pos, y_pos))
        self.num_stones += 1
        self.current_turn_placements += 1

        # Switch turn only after required placements for this turn.
        if self.current_turn_placements >= self.stones_to_place:
            self.turn *= -1
            self.current_turn_placements = 0
            self.stones_to_place = 2

    def get_remaining_stones(self):
        """Number of stones still required for the current turn."""
        return self.stones_to_place - self.current_turn_placements
