"""Standard 7x6 Connect Four, with bounded iterative-deepening alpha-beta search.

Bits run bottom to top in each column, with one unused sentinel bit per column.
``current`` always contains the pieces belonging to the side about to move.
"""

from dataclasses import dataclass
from math import isfinite
from time import perf_counter

WIDTH, HEIGHT = 7, 6
STRIDE = HEIGHT + 1
COLUMNS = tuple(((1 << HEIGHT) - 1) << (STRIDE * c) for c in range(WIDTH))
BOTTOM = tuple(1 << (STRIDE * c) for c in range(WIDTH))
BOTTOM_MASK = sum(BOTTOM)
BOARD_MASK = sum(COLUMNS)
CENTER_ORDER = (3, 2, 4, 1, 5, 0, 6)
MATE = 1_000_000


def has_four(bits: int) -> bool:
    for shift in (1, STRIDE, STRIDE - 1, STRIDE + 1):
        pairs = bits & (bits >> shift)
        if pairs & (pairs >> (2 * shift)):
            return True
    return False


def winning_cells(bits: int, occupied: int) -> int:
    result = 0
    for d in (1, STRIDE, STRIDE - 1, STRIDE + 1):
        result |= (bits << d) & (bits << (2 * d)) & (bits << (3 * d))
        result |= (bits >> d) & (bits << d) & (bits << (2 * d))
        result |= (bits >> (2 * d)) & (bits >> d) & (bits << d)
        result |= (bits >> (3 * d)) & (bits >> (2 * d)) & (bits >> d)
    return result & BOARD_MASK & ~occupied


def _mirror(bits: int) -> int:
    return sum(((bits >> (STRIDE * c)) & 127) << (STRIDE * (6 - c)) for c in range(7))


@dataclass(frozen=True, slots=True)
class Position:
    current: int = 0
    occupied: int = 0

    @classmethod
    def from_moves(cls, moves) -> "Position":
        position = cls()
        for column in moves:
            position = position.play(column)
        return position

    @classmethod
    def from_rows(cls, rows) -> "Position":
        if len(rows) != HEIGHT or any(len(row) != WIDTH for row in rows):
            raise ValueError("board must have six rows of seven cells (top row first)")
        pieces = [0, 0, 0]
        for c in range(WIDTH):
            empty_seen = False
            for r in range(HEIGHT):
                cell = rows[HEIGHT - 1 - r][c]
                if type(cell) is not int or cell not in (0, 1, 2):
                    raise ValueError("board cells must be integers 0, 1 or 2")
                if not cell:
                    empty_seen = True
                elif empty_seen:
                    raise ValueError("floating piece violates gravity")
                else:
                    pieces[cell] |= 1 << (STRIDE * c + r)
        first, second = pieces[1:]
        a, b = first.bit_count(), second.bit_count()
        if a not in (b, b + 1):
            raise ValueError("piece counts do not alternate from player 1")
        if has_four(first) and (has_four(second) or a != b + 1):
            raise ValueError("invalid winning board")
        if has_four(second) and a != b:
            raise ValueError("invalid winning board")
        current = first if a == b else second
        position = cls(current, first | second)
        if position.winner() is not None:
            # At least one topmost last-player piece must explain the terminal win.
            last = position.opponent
            if not any(
                (top := 1 << (STRIDE * c + ((position.occupied & COLUMNS[c]).bit_count() - 1))) & last
                and not has_four(last ^ top)
                for c in range(WIDTH) if position.occupied & COLUMNS[c]
            ):
                raise ValueError("board contains moves after an earlier win")
        return position

    @property
    def opponent(self) -> int:
        return self.occupied ^ self.current

    @property
    def player(self) -> int:
        return 1 + (self.occupied.bit_count() % 2)

    def possible_mask(self) -> int:
        return (self.occupied + BOTTOM_MASK) & BOARD_MASK

    def legal_moves(self) -> list[int]:
        if self.winner() is not None:
            return []
        possible = self.possible_mask()
        return [c for c in CENTER_ORDER if possible & COLUMNS[c]]

    def winner(self) -> int | None:
        if has_four(self.opponent):
            return 3 - self.player
        if has_four(self.current):
            return self.player
        return None

    def play(self, column: int) -> "Position":
        if type(column) is not int or not 0 <= column < WIDTH:
            raise ValueError("column must be an integer from 0 through 6")
        if self.winner() is not None:
            raise ValueError("cannot play after the game is over")
        move = self.possible_mask() & COLUMNS[column]
        if not move:
            raise ValueError("column is full")
        return self._play_bit(move)

    def _play_bit(self, move: int) -> "Position":
        return Position(self.opponent, self.occupied | move)

    def safe_mask(self) -> int:
        """Non-losing moves, provided the current player has no immediate win."""
        possible = self.possible_mask()
        opponent_wins = winning_cells(self.opponent, self.occupied)
        forced = possible & opponent_wins
        if forced:
            if forced & (forced - 1):
                return 0
            possible = forced
        return possible & ~(opponent_wins >> 1)

    def rows(self) -> list[list[int]]:
        first = self.current if self.player == 1 else self.opponent
        second = self.occupied ^ first
        return [
            [1 if first & (1 << (STRIDE * c + r)) else
             2 if second & (1 << (STRIDE * c + r)) else 0 for c in range(WIDTH)]
            for r in reversed(range(HEIGHT))
        ]


def _windows():
    masks = []
    for c in range(WIDTH):
        for r in range(HEIGHT):
            for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
                if 0 <= c + 3 * dc < WIDTH and 0 <= r + 3 * dr < HEIGHT:
                    masks.append(sum(1 << (STRIDE * (c + dc * i) + r + dr * i) for i in range(4)))
    return tuple(masks)


WINDOWS = _windows()
WEIGHTS = (0, 2, 15, 90, 0)


def evaluate(position: Position) -> int:
    own, other = position.current, position.opponent
    value = 5 * ((own & COLUMNS[3]).bit_count() - (other & COLUMNS[3]).bit_count())
    for window in WINDOWS:
        a, b = own & window, other & window
        if not b:
            value += WEIGHTS[a.bit_count()]
        elif not a:
            value -= WEIGHTS[b.bit_count()]
    return value


@dataclass(slots=True)
class SearchResult:
    column: int | None
    score: int
    depth: int
    nodes: int
    elapsed_ms: float
    solved: bool
    reason: str


class _BudgetExceeded(Exception):
    pass


class Connect4Agent:
    def __init__(self, time_limit_ms=250, max_depth=42, max_nodes=500_000):
        if (type(time_limit_ms) not in (int, float) or not isfinite(time_limit_ms) or time_limit_ms <= 0
                or type(max_depth) is not int or max_depth < 1
                or type(max_nodes) is not int or max_nodes < 1):
            raise ValueError("search limits must be positive")
        self.time_limit_ms = min(float(time_limit_ms), 60_000)
        self.max_depth = min(int(max_depth), 42)
        self.max_nodes = int(max_nodes)
        self.table = {}

    def choose(self, position: Position) -> SearchResult:
        started = perf_counter()
        self.deadline = started + self.time_limit_ms / 1000
        self.nodes = 0
        self.table.clear()
        legal = position.legal_moves()
        if not legal:
            score = -MATE if position.winner() is not None else 0
            return SearchResult(None, score, 0, 0, 0, True, "terminal")
        possible = position.possible_mask()
        wins = winning_cells(position.current, position.occupied) & possible
        if wins:
            column = next(c for c in CENTER_ORDER if wins & COLUMNS[c])
            return SearchResult(column, MATE - 1, 1, 0, (perf_counter() - started) * 1000, True, "immediate_win")
        safe = position.safe_mask()
        if not safe:
            return SearchResult(legal[0], -MATE + 2, 2, 0, (perf_counter() - started) * 1000, True, "forced_loss")
        candidates = [c for c in CENTER_ORDER if safe & COLUMNS[c]]
        best = candidates[0]
        score, depth_done, solved = evaluate(position), 0, False
        remaining = 42 - position.occupied.bit_count()
        for depth in range(1, min(self.max_depth, remaining) + 1):
            try:
                self._check_budget()
                value, column = self._root(position, depth, best)
            except _BudgetExceeded:
                break
            best, score, depth_done = column, value, depth
            if abs(score) >= MATE - 42 or depth == remaining:
                solved = True
                break
        return SearchResult(best, score, depth_done, self.nodes, (perf_counter() - started) * 1000,
                            solved, "proven" if solved else "bounded_search")

    def _check_budget(self):
        if self.nodes >= self.max_nodes or perf_counter() >= self.deadline:
            raise _BudgetExceeded

    def _root(self, position, depth, preferred):
        safe = position.safe_mask()
        alpha, best = -MATE, preferred
        ordered = [preferred] + [c for c in CENTER_ORDER if c != preferred]
        for c in ordered:
            move = safe & COLUMNS[c]
            if not move:
                continue
            self._check_budget()
            value = -self._search(position._play_bit(move), depth - 1, -MATE, -alpha, 1)
            if value > alpha:
                alpha, best = value, c
        return alpha, best

    def _search(self, position, depth, alpha, beta, ply):
        self.nodes += 1
        if self.nodes % 128 == 0 or self.nodes >= self.max_nodes:
            self._check_budget()
        possible = position.possible_mask()
        if not possible:
            return 0
        if winning_cells(position.current, position.occupied) & possible:
            return MATE - ply - 1
        safe = position.safe_mask()
        if not safe:
            return -MATE + ply + 2
        if depth <= 0:
            return evaluate(position)
        original_alpha, original_beta = alpha, beta
        # Normalize mirror images, including the stored best column.
        raw = (position.current, position.occupied)
        mirrored = (_mirror(position.current), _mirror(position.occupied))
        flip = mirrored < raw
        key = mirrored if flip else raw
        entry = self.table.get(key)
        preferred = None
        if entry:
            stored_depth, value, bound, canonical_column = entry
            preferred = 6 - canonical_column if flip else canonical_column
            if stored_depth >= depth:
                if bound == "exact":
                    return value
                if bound == "lower":
                    alpha = max(alpha, value)
                else:
                    beta = min(beta, value)
                if alpha >= beta:
                    return value
        best, best_column = -MATE, 3
        ordered = ([preferred] if preferred is not None else []) + [c for c in CENTER_ORDER if c != preferred]
        for c in ordered:
            move = safe & COLUMNS[c]
            if not move:
                continue
            value = -self._search(position._play_bit(move), depth - 1, -beta, -alpha, ply + 1)
            if value > best:
                best, best_column = value, c
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        bound = "upper" if best <= original_alpha else "lower" if best >= original_beta else "exact"
        if len(self.table) < 200_000:
            self.table[key] = (depth, best, bound, 6 - best_column if flip else best_column)
        return best
