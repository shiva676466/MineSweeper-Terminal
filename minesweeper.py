#!/usr/bin/env python3
import curses
import random
import time
import sys
import json
import os
from collections import deque

CELL_W = 3
SCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".minesweeper_scores.json")

UNREVEALED  = "███"
REVEALED_0  = "   "
MINE_CH     = " ✹ "
FLAG_CH     = " ⚑ "
QUESTION_CH = " ? "
EXPLODED_CH = "█✹█"
WRONG_FLAG  = " ✗ "

DIFFICULTIES = [
    ("Easy",    9,  9,  10),
    ("Medium", 16, 16,  40),
    ("Hard",   16, 30,  99),
    ("Custom",  0,  0,   0),
]

TITLE_ART = [
    "┌─────────────────────────────────────────┐",
    "│                                         │",
    "│   ✹  M I N E S W E E P E R  ✹   │",
    "│                                         │",
    "└─────────────────────────────────────────┘",
]


class Minesweeper:
    def __init__(self, rows=16, cols=30, mines=99):
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.board = [[0] * cols for _ in range(rows)]
        self.revealed = [[False] * cols for _ in range(rows)]
        self.flagged = [[False] * cols for _ in range(rows)]
        self.question = [[False] * cols for _ in range(rows)]
        self.cursor_r = rows // 2
        self.cursor_c = cols // 2
        self.game_over = False
        self.won = False
        self.first_move = True
        self.start_time = None
        self.end_time = None
        self.exploded = None
        self.reveal_queue = []
        self.cells_revealed = 0
        self.total_safe = rows * cols - mines

    def place_mines(self, safe_r, safe_c):
        safe = set()
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                safe.add((safe_r + dr, safe_c + dc))

        positions = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in safe]
        mine_positions = random.sample(positions, self.mines)

        for r, c in mine_positions:
            self.board[r][c] = -1

        for r in range(self.rows):
            for c in range(self.cols):
                if self.board[r][c] == -1:
                    continue
                count = 0
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols and self.board[nr][nc] == -1:
                            count += 1
                self.board[r][c] = count

    def reveal(self, r, c):
        if self.revealed[r][c] or self.flagged[r][c]:
            return []
        if self.first_move:
            self.place_mines(r, c)
            self.first_move = False
            self.start_time = time.time()

        newly = []
        queue = deque([(r, c)])
        visited = set()

        while queue:
            cr, cc = queue.popleft()
            if (cr, cc) in visited:
                continue
            if self.revealed[cr][cc] or self.flagged[cr][cc]:
                continue
            visited.add((cr, cc))

            self.revealed[cr][cc] = True
            self.question[cr][cc] = False
            self.cells_revealed += 1
            newly.append((cr, cc))

            if self.board[cr][cc] == -1:
                self.game_over = True
                self.exploded = (cr, cc)
                self.end_time = time.time()
                return newly

            if self.board[cr][cc] == 0:
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < self.rows and 0 <= nc < self.cols:
                            queue.append((nr, nc))

        self.check_win()
        return newly

    def chord(self, r, c):
        if not self.revealed[r][c] or self.board[r][c] <= 0:
            return []
        flag_count = 0
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols and self.flagged[nr][nc]:
                    flag_count += 1
        if flag_count == self.board[r][c]:
            newly = []
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.rows and 0 <= nc < self.cols:
                        newly.extend(self.reveal(nr, nc))
            return newly
        return []

    def cycle_mark(self, r, c):
        if self.revealed[r][c]:
            return
        if not self.flagged[r][c] and not self.question[r][c]:
            self.flagged[r][c] = True
        elif self.flagged[r][c]:
            self.flagged[r][c] = False
            self.question[r][c] = True
        else:
            self.question[r][c] = False

    def toggle_flag(self, r, c):
        if not self.revealed[r][c]:
            if self.question[r][c]:
                self.question[r][c] = False
            self.flagged[r][c] = not self.flagged[r][c]

    def check_win(self):
        if self.cells_revealed == self.total_safe:
            self.won = True
            self.game_over = True
            self.end_time = time.time()

    @property
    def flags_remaining(self):
        count = sum(self.flagged[r][c] for r in range(self.rows) for c in range(self.cols))
        return self.mines - count

    @property
    def elapsed(self):
        if self.start_time is None:
            return 0
        end = self.end_time if self.end_time else time.time()
        return int(end - self.start_time)

    @property
    def progress(self):
        if self.total_safe == 0:
            return 100
        return int(self.cells_revealed / self.total_safe * 100)


def load_scores():
    try:
        with open(SCORE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_score(difficulty, seconds):
    scores = load_scores()
    if difficulty not in scores:
        scores[difficulty] = []
    scores[difficulty].append({"time": seconds, "date": time.strftime("%Y-%m-%d %H:%M")})
    scores[difficulty].sort(key=lambda x: x["time"])
    scores[difficulty] = scores[difficulty][:10]
    with open(SCORE_FILE, "w") as f:
        json.dump(scores, f, indent=2)


def init_colors():
    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color():
        curses.init_color(20, 200, 200, 200)
        curses.init_color(21, 700, 700, 700)
        curses.init_color(22, 100, 100, 100)
        curses.init_color(23, 300, 300, 300)
        curses.init_color(24, 50, 50, 50)
        unrevealed_bg = 20
        revealed_bg = 22
        mid_gray = 23
        dark_bg = 24
    else:
        unrevealed_bg = curses.COLOR_WHITE
        revealed_bg = curses.COLOR_BLACK
        mid_gray = curses.COLOR_WHITE
        dark_bg = curses.COLOR_BLACK

    curses.init_pair(1, curses.COLOR_BLUE, revealed_bg)
    curses.init_pair(2, curses.COLOR_GREEN, revealed_bg)
    curses.init_pair(3, curses.COLOR_RED, revealed_bg)
    curses.init_pair(4, curses.COLOR_MAGENTA, revealed_bg)
    curses.init_pair(5, curses.COLOR_YELLOW, revealed_bg)
    curses.init_pair(6, curses.COLOR_CYAN, revealed_bg)
    curses.init_pair(7, curses.COLOR_WHITE, revealed_bg)
    curses.init_pair(8, curses.COLOR_WHITE, revealed_bg)

    curses.init_pair(10, unrevealed_bg, unrevealed_bg)
    curses.init_pair(11, revealed_bg, revealed_bg)
    curses.init_pair(12, curses.COLOR_RED, unrevealed_bg)
    curses.init_pair(13, curses.COLOR_RED, revealed_bg)
    curses.init_pair(14, curses.COLOR_RED, curses.COLOR_RED)

    curses.init_pair(15, curses.COLOR_BLACK, curses.COLOR_CYAN)
    curses.init_pair(16, curses.COLOR_BLACK, curses.COLOR_CYAN)

    curses.init_pair(17, curses.COLOR_GREEN, -1)
    curses.init_pair(18, curses.COLOR_RED, -1)
    curses.init_pair(19, curses.COLOR_WHITE, -1)

    curses.init_pair(20, mid_gray, -1)
    curses.init_pair(21, curses.COLOR_YELLOW, -1)
    curses.init_pair(22, curses.COLOR_CYAN, -1)

    curses.init_pair(23, curses.COLOR_YELLOW, unrevealed_bg)   # question mark
    curses.init_pair(24, curses.COLOR_RED, dark_bg)            # wrong flag
    curses.init_pair(25, curses.COLOR_GREEN, revealed_bg)      # animation flash
    curses.init_pair(26, curses.COLOR_YELLOW, -1)              # progress bar filled
    curses.init_pair(27, mid_gray, -1)                         # progress bar empty
    curses.init_pair(28, curses.COLOR_WHITE, curses.COLOR_RED) # explosion ring
    curses.init_pair(29, curses.COLOR_CYAN, -1)                # score highlight


def sa(stdscr, y, x, text, attr):
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h or x >= w:
        return
    if x + len(text) > w:
        text = text[:w - x]
    if not text:
        return
    try:
        stdscr.addstr(y, x, text, attr)
    except curses.error:
        pass


def make_hline(cols, left, mid, right, seg="───"):
    return left + mid.join([seg] * cols) + right


def get_cell_display(game, r, c, anim_cells=None):
    if game.revealed[r][c]:
        val = game.board[r][c]
        if val == -1:
            if game.exploded == (r, c):
                return EXPLODED_CH, curses.color_pair(14) | curses.A_BOLD
            else:
                return MINE_CH, curses.color_pair(13) | curses.A_BOLD
        elif val == 0:
            return REVEALED_0, curses.color_pair(11)
        else:
            if anim_cells and (r, c) in anim_cells:
                return f" {val} ", curses.color_pair(25) | curses.A_BOLD
            return f" {val} ", curses.color_pair(val) | curses.A_BOLD
    elif game.flagged[r][c]:
        if game.game_over and not game.won and game.board[r][c] != -1:
            return WRONG_FLAG, curses.color_pair(24) | curses.A_BOLD
        return FLAG_CH, curses.color_pair(12) | curses.A_BOLD
    elif game.question[r][c]:
        return QUESTION_CH, curses.color_pair(23) | curses.A_BOLD
    elif game.game_over and game.board[r][c] == -1:
        return MINE_CH, curses.color_pair(13)
    else:
        return UNREVEALED, curses.color_pair(10)


def draw_board(stdscr, game, col_offset, row_offset, board_w, anim_cells=None):
    border_attr = curses.color_pair(20)

    sa(stdscr, row_offset - 1, col_offset, make_hline(game.cols, "┌", "┬", "┐"), border_attr)

    for r in range(game.rows):
        y = row_offset + r * 2

        sa(stdscr, y, col_offset, "│", border_attr)
        for c in range(game.cols):
            x = col_offset + 1 + c * (CELL_W + 1)
            is_cursor = (r == game.cursor_r and c == game.cursor_c)

            ch, attr = get_cell_display(game, r, c, anim_cells)

            if is_cursor and not game.game_over:
                if game.revealed[r][c]:
                    val = game.board[r][c]
                    ch = f">{val}<" if val > 0 else "> <"
                elif game.flagged[r][c]:
                    ch = ">⚑<"
                elif game.question[r][c]:
                    ch = ">?<"
                else:
                    ch = ">█<"
                attr = curses.color_pair(15) | curses.A_BOLD

            sa(stdscr, y, x, ch, attr)
            sa(stdscr, y, x + CELL_W, "│", border_attr)

        if r < game.rows - 1:
            sa(stdscr, y + 1, col_offset, make_hline(game.cols, "├", "┼", "┤"), border_attr)

    bot_y = row_offset + (game.rows - 1) * 2 + 1
    sa(stdscr, bot_y, col_offset, make_hline(game.cols, "└", "┴", "┘"), border_attr)
    return bot_y


def draw_progress_bar(stdscr, y, x, width, pct, attr_fill, attr_empty):
    filled = int(width * pct / 100)
    sa(stdscr, y, x, "▓" * filled, attr_fill)
    sa(stdscr, y, x + filled, "░" * (width - filled), attr_empty)


def draw(stdscr, game, anim_cells=None, difficulty_name=""):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    board_w = game.cols * (CELL_W + 1) + 1
    col_offset = max(0, (w - board_w) // 2)
    row_offset = 4

    # header
    header_y = row_offset - 3
    mine_str = f" ⚑ {game.flags_remaining:3d}"
    time_str = f" ⏱ {game.elapsed:3d}s"
    sa(stdscr, header_y, col_offset + 1, mine_str, curses.color_pair(21) | curses.A_BOLD)
    sa(stdscr, header_y, col_offset + board_w - len(time_str) - 1, time_str, curses.color_pair(22) | curses.A_BOLD)

    if difficulty_name:
        sa(stdscr, header_y, col_offset + (board_w - len(difficulty_name)) // 2, difficulty_name, curses.A_DIM)

    if not game.first_move:
        face = " ☺ " if not game.game_over else (" ☻ " if game.won else " ☹ ")
        face_x = col_offset + (board_w - 3) // 2
        face_attr = curses.color_pair(17 if game.won else (18 if game.game_over else 19)) | curses.A_BOLD
        sa(stdscr, header_y, face_x, face, face_attr)

    # progress bar
    prog_y = row_offset - 2
    bar_w = min(board_w - 2, 40)
    bar_x = col_offset + (board_w - bar_w - 6) // 2
    pct = game.progress
    sa(stdscr, prog_y, bar_x, f"{pct:3d}% ", curses.color_pair(22))
    draw_progress_bar(stdscr, prog_y, bar_x + 5, bar_w, pct,
                      curses.color_pair(26), curses.color_pair(27))

    # board
    bot_y = draw_board(stdscr, game, col_offset, row_offset, board_w, anim_cells)

    # status
    status_y = bot_y + 2
    if game.game_over:
        if game.won:
            msg = "★ ★ ★  YOU WIN!  ★ ★ ★"
            attr = curses.color_pair(17) | curses.A_BOLD
        else:
            msg = "☠  GAME OVER  ☠"
            attr = curses.color_pair(18) | curses.A_BOLD
        sa(stdscr, status_y, col_offset + (board_w - len(msg)) // 2, msg, attr)

        time_msg = f"Time: {game.elapsed}s"
        sa(stdscr, status_y + 1, col_offset + (board_w - len(time_msg)) // 2, time_msg, curses.A_DIM)

        restart_msg = "[R] Restart   [N] New Difficulty   [S] Scores   [Q] Quit"
        sa(stdscr, status_y + 2, col_offset + (board_w - len(restart_msg)) // 2, restart_msg, curses.A_DIM)
    else:
        line1 = "[Space] Reveal  [F] Flag  [M] Flag/? Cycle  [C] Chord"
        line2 = "[R] Restart  [N] New Difficulty  [Q] Quit"
        sa(stdscr, status_y, col_offset + (board_w - len(line1)) // 2, line1, curses.A_DIM)
        sa(stdscr, status_y + 1, col_offset + (board_w - len(line2)) // 2, line2, curses.A_DIM)

    stdscr.refresh()


def animate_reveal(stdscr, game, newly_revealed, difficulty_name):
    if not newly_revealed or len(newly_revealed) < 3:
        return

    batch_size = max(1, len(newly_revealed) // 8)
    for i in range(0, len(newly_revealed), batch_size):
        batch = set(newly_revealed[i:i + batch_size])
        draw(stdscr, game, anim_cells=batch, difficulty_name=difficulty_name)
        time.sleep(0.02)
    draw(stdscr, game, difficulty_name=difficulty_name)


def animate_explosion(stdscr, game, difficulty_name):
    if not game.exploded:
        return

    er, ec = game.exploded
    max_dist = max(game.rows, game.cols)

    for dist in range(max_dist + 1):
        for r in range(game.rows):
            for c in range(game.cols):
                d = abs(r - er) + abs(c - ec)
                if d == dist and game.board[r][c] == -1 and (r, c) != game.exploded:
                    game.revealed[r][c] = True
        draw(stdscr, game, difficulty_name=difficulty_name)
        delay = 0.04 if dist < 5 else 0.02
        time.sleep(delay)


def animate_win(stdscr, game, difficulty_name):
    h, w = stdscr.getmaxyx()
    board_w = game.cols * (CELL_W + 1) + 1
    col_offset = max(0, (w - board_w) // 2)

    sparkle_chars = ["✦", "✧", "★", "☆", "·"]
    for frame in range(12):
        draw(stdscr, game, difficulty_name=difficulty_name)
        for _ in range(5):
            sy = random.randint(0, h - 1)
            sx = random.randint(col_offset, col_offset + board_w - 1)
            ch = random.choice(sparkle_chars)
            color = random.choice([17, 21, 22, 29])
            sa(stdscr, sy, sx, ch, curses.color_pair(color) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(0.12)


def show_scores(stdscr):
    scores = load_scores()
    curses.curs_set(0)
    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        title = "━━━  HIGH SCORES  ━━━"
        sa(stdscr, 1, (w - len(title)) // 2, title, curses.color_pair(22) | curses.A_BOLD)

        y = 3
        for diff_name in ["Easy", "Medium", "Hard"]:
            sa(stdscr, y, (w - len(diff_name)) // 2, diff_name, curses.color_pair(21) | curses.A_BOLD)
            y += 1

            entries = scores.get(diff_name, [])
            if not entries:
                sa(stdscr, y, (w - 14) // 2, "No scores yet", curses.A_DIM)
                y += 1
            else:
                for i, entry in enumerate(entries[:5]):
                    rank = f"  {i+1}. {entry['time']:4d}s   {entry['date']}  "
                    attr = curses.color_pair(29) | curses.A_BOLD if i == 0 else curses.A_DIM
                    sa(stdscr, y, (w - len(rank)) // 2, rank, attr)
                    y += 1
            y += 1

        hint = "Press any key to return"
        sa(stdscr, y + 1, (w - len(hint)) // 2, hint, curses.A_DIM)
        stdscr.refresh()
        stdscr.getch()
        break


def input_number(stdscr, prompt, y, x, min_val, max_val):
    sa(stdscr, y, x, prompt, curses.A_BOLD)
    stdscr.refresh()
    curses.echo()
    curses.curs_set(1)
    try:
        s = stdscr.getstr(y, x + len(prompt), 5).decode()
        val = int(s)
        return max(min_val, min(max_val, val))
    except (ValueError, curses.error):
        return min_val
    finally:
        curses.noecho()
        curses.curs_set(0)


def select_difficulty(stdscr):
    curses.curs_set(0)
    init_colors()
    selected = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        title_y = h // 2 - 8
        for i, line in enumerate(TITLE_ART):
            cx = max(0, (w - len(line)) // 2)
            sa(stdscr, title_y + i, cx, line, curses.color_pair(22) | curses.A_BOLD)

        scores = load_scores()

        for i, (name, rows, cols, mines) in enumerate(DIFFICULTIES):
            if name == "Custom":
                label = f"  {'Custom':8s}  Set your own        "
            else:
                label = f"  {name:8s}  {cols}×{rows}   {mines:2d} mines  "
                best = scores.get(name, [])
                if best:
                    label += f"  Best: {best[0]['time']}s"

            y = h // 2 - 1 + i * 2
            x = max(0, (w - max(40, len(label))) // 2)
            attr = curses.color_pair(15) | curses.A_BOLD if i == selected else curses.A_DIM
            sa(stdscr, y, x, label, attr)

        hint = "↑↓ Select   Enter Start   S Scores   Q Quit"
        sa(stdscr, h // 2 + 8, max(0, (w - len(hint)) // 2), hint, curses.A_DIM)

        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            selected = (selected - 1) % len(DIFFICULTIES)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = (selected + 1) % len(DIFFICULTIES)
        elif key in (ord('s'), ord('S')):
            show_scores(stdscr)
        elif key in (curses.KEY_ENTER, 10, 13):
            name, rows, cols, mines = DIFFICULTIES[selected]
            if name == "Custom":
                stdscr.erase()
                cy = h // 2 - 2
                cx = w // 2 - 15
                rows = input_number(stdscr, "Rows (5-30): ", cy, cx, 5, 30)
                cols = input_number(stdscr, "Cols (5-50): ", cy + 2, cx, 5, 50)
                max_mines = (rows * cols) - 9
                mines = input_number(stdscr, f"Mines (1-{max_mines}): ", cy + 4, cx, 1, max_mines)
                return rows, cols, mines, "Custom"
            return rows, cols, mines, name
        elif key in (ord('q'), ord('Q'), 27):
            return None, None, None, None


def main(stdscr):
    curses.curs_set(0)
    init_colors()
    sys.setrecursionlimit(10000)

    result = select_difficulty(stdscr)
    if result[0] is None:
        return
    rows, cols, mines, diff_name = result

    game = Minesweeper(rows, cols, mines)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    while True:
        draw(stdscr, game, difficulty_name=diff_name)

        key = stdscr.getch()
        if key == -1:
            continue

        if key in (ord('q'), ord('Q')):
            break
        elif key in (ord('n'), ord('N')):
            stdscr.nodelay(False)
            stdscr.timeout(-1)
            result = select_difficulty(stdscr)
            if result[0] is None:
                break
            rows, cols, mines, diff_name = result
            game = Minesweeper(rows, cols, mines)
            stdscr.nodelay(True)
            stdscr.timeout(100)
            continue
        elif key in (ord('r'), ord('R')):
            game = Minesweeper(rows, cols, mines)
            continue
        elif key in (ord('s'), ord('S')) and game.game_over:
            stdscr.nodelay(False)
            stdscr.timeout(-1)
            show_scores(stdscr)
            stdscr.nodelay(True)
            stdscr.timeout(100)
            continue

        if game.game_over:
            continue

        if key in (curses.KEY_UP, ord('k'), ord('w')):
            game.cursor_r = (game.cursor_r - 1) % game.rows
        elif key in (curses.KEY_DOWN, ord('j'), ord('s')):
            game.cursor_r = (game.cursor_r + 1) % game.rows
        elif key in (curses.KEY_LEFT, ord('h'), ord('a')):
            game.cursor_c = (game.cursor_c - 1) % game.cols
        elif key in (curses.KEY_RIGHT, ord('l'), ord('d')):
            game.cursor_c = (game.cursor_c + 1) % game.cols
        elif key == ord(' '):
            stdscr.nodelay(False)
            newly = game.reveal(game.cursor_r, game.cursor_c)
            if game.game_over and not game.won:
                animate_explosion(stdscr, game, diff_name)
            elif newly:
                animate_reveal(stdscr, game, newly, diff_name)
            if game.won:
                if diff_name != "Custom":
                    save_score(diff_name, game.elapsed)
                animate_win(stdscr, game, diff_name)
            stdscr.nodelay(True)
            stdscr.timeout(100)
        elif key in (ord('f'), ord('F')):
            game.toggle_flag(game.cursor_r, game.cursor_c)
        elif key in (ord('m'), ord('M')):
            game.cycle_mark(game.cursor_r, game.cursor_c)
        elif key in (ord('c'), ord('C')):
            stdscr.nodelay(False)
            newly = game.chord(game.cursor_r, game.cursor_c)
            if game.game_over and not game.won:
                animate_explosion(stdscr, game, diff_name)
            elif newly:
                animate_reveal(stdscr, game, newly, diff_name)
            if game.won:
                if diff_name != "Custom":
                    save_score(diff_name, game.elapsed)
                animate_win(stdscr, game, diff_name)
            stdscr.nodelay(True)
            stdscr.timeout(100)


if __name__ == "__main__":
    curses.wrapper(main)
