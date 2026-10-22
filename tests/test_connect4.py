import random
import unittest
from functools import lru_cache

from agents.connect4 import (Connect4Agent, Position, COLUMNS, winning_cells,
                             has_four, MATE, WINDOWS)


def grid_winner(board):
    for r in range(6):
        for c in range(7):
            player = board[r][c]
            if not player:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                if 0 <= r + 3 * dr < 6 and 0 <= c + 3 * dc < 7:
                    if all(board[r + k * dr][c + k * dc] == player for k in range(4)):
                        return player
    return None


def grid_drop(board, column, player):
    child = [list(row) for row in board]
    for r in reversed(range(6)):
        if child[r][column] == 0:
            child[r][column] = player
            return child
    raise ValueError("full")


@lru_cache(maxsize=None)
def oracle(board, player, ply=0):
    if grid_winner(board):
        return -MATE + ply
    legal = [c for c in range(7) if board[0][c] == 0]
    if not legal:
        return 0
    return max(-oracle(tuple(map(tuple, grid_drop(board, c, player))), 3 - player, ply + 1) for c in legal)


class Connect4Tests(unittest.TestCase):
    def test_immediate_win(self):
        result = Connect4Agent().choose(Position.from_moves([0, 1, 0, 1, 0, 2]))
        self.assertEqual(result.column, 0)
        self.assertTrue(result.solved)

    def test_must_block(self):
        result = Connect4Agent(time_limit_ms=50).choose(Position.from_moves([3, 0, 3, 0, 6, 0]))
        self.assertEqual(result.column, 0)

    def test_window_count(self):
        self.assertEqual(len(WINDOWS), 69)
        self.assertEqual(len(set(WINDOWS)), 69)

    def test_terminal_and_invalid_moves(self):
        p = Position.from_moves([0, 1, 0, 1, 0, 1, 0])
        self.assertEqual(p.winner(), 1)
        self.assertIsNone(Connect4Agent().choose(p).column)
        with self.assertRaises(ValueError):
            p.play(4)
        for c in (-1, 7, True, "3"):
            with self.assertRaises(ValueError):
                Position().play(c)
        with self.assertRaises(ValueError):
            Position.from_moves([0] * 7)

    def test_invalid_boards(self):
        board = [[0] * 7 for _ in range(6)]
        board[0][0] = 1
        with self.assertRaises(ValueError):
            Position.from_rows(board)
        board = [[0] * 7 for _ in range(6)]
        board[-1][0] = 2
        with self.assertRaises(ValueError):
            Position.from_rows(board)

    def test_random_differential_move_logic(self):
        rng = random.Random(1203)
        checked = 0
        for _ in range(150):
            p = Position()
            while p.legal_moves():
                board = p.rows()
                self.assertEqual(Position.from_rows(board), p)
                self.assertEqual(grid_winner(board), p.winner())
                wins = winning_cells(p.current, p.occupied) & p.possible_mask()
                for c in p.legal_moves():
                    child = grid_drop(board, c, p.player)
                    self.assertEqual(bool(wins & COLUMNS[c]), grid_winner(child) == p.player)
                if not wins:
                    expected = []
                    for c in p.legal_moves():
                        child = grid_drop(board, c, p.player)
                        loses = any(grid_winner(grid_drop(child, other, 3 - p.player)) == 3 - p.player
                                    for other in range(7) if child[0][other] == 0)
                        if not loses:
                            expected.append(c)
                    actual = [c for c in p.legal_moves() if p.safe_mask() & COLUMNS[c]]
                    self.assertEqual(expected, actual)
                p = p.play(rng.choice(p.legal_moves()))
                checked += 1
        self.assertGreater(checked, 2000)

    def test_endgames_against_independent_exhaustive_oracle(self):
        rng = random.Random(104)
        cases = []
        for _ in range(1000):
            p = Position()
            while p.occupied.bit_count() < 36:
                nonwinning = [c for c in p.legal_moves() if p.play(c).winner() is None]
                if not nonwinning:
                    break
                p = p.play(rng.choice(nonwinning))
            if p.occupied.bit_count() >= 36 and p.legal_moves():
                cases.append(p)
                if len(cases) == 16:
                    break
        self.assertEqual(len(cases), 16)
        for p in cases:
            board = tuple(map(tuple, p.rows()))
            expected = oracle(board, p.player)
            result = Connect4Agent(time_limit_ms=2000).choose(p)
            selected = -oracle(tuple(map(tuple, grid_drop(board, result.column, p.player))), 3 - p.player, 1)
            self.assertEqual(selected, expected, (board, result))
            self.assertEqual(result.score, expected)
            self.assertTrue(result.solved)
        oracle.cache_clear()

    def test_budget_always_returns_legal_fallback(self):
        for time_ms, nodes in ((.001, 1), (10, 32), (50, 1000)):
            result = Connect4Agent(time_limit_ms=time_ms, max_nodes=nodes).choose(Position())
            self.assertIn(result.column, Position().legal_moves())
            self.assertLessEqual(result.nodes, nodes)
            self.assertLess(result.elapsed_ms, 1000)

    def test_mirrored_tactics(self):
        moves = [0, 1, 0, 1, 0, 2]
        result = Connect4Agent().choose(Position.from_moves([6 - c for c in moves]))
        self.assertEqual(result.column, 6)


if __name__ == "__main__":
    unittest.main()
