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
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".minesweeper_config.json")

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

# ── Color Themes ──────────────────────────────────────────────

THEMES = {
    "Classic": {
        "unrevealed_rgb": (200, 200, 200),
        "revealed_rgb":   (100, 100, 100),
        "mid_gray_rgb":   (300, 300, 300),
        "dark_rgb":       (50,  50,  50),
        "border_fg": None,
        "num_colors": {
            1: curses.COLOR_BLUE,   2: curses.COLOR_GREEN,
            3: curses.COLOR_RED,    4: curses.COLOR_MAGENTA,
            5: curses.COLOR_YELLOW, 6: curses.COLOR_CYAN,
            7: curses.COLOR_WHITE,  8: curses.COLOR_WHITE,
        },
    },
    "Dracula": {
        "unrevealed_rgb": (170, 130, 310),
        "revealed_rgb":   (110,  90, 200),
        "mid_gray_rgb":   (240, 200, 370),
        "dark_rgb":       (80,   60, 150),
        "border_fg": None,
        "num_colors": {
            1: curses.COLOR_CYAN,    2: curses.COLOR_GREEN,
            3: curses.COLOR_RED,     4: curses.COLOR_MAGENTA,
            5: curses.COLOR_YELLOW,  6: curses.COLOR_CYAN,
            7: curses.COLOR_WHITE,   8: curses.COLOR_WHITE,
        },
    },
    "Retro": {
        "unrevealed_rgb": (0,   300, 0),
        "revealed_rgb":   (0,   80,  0),
        "mid_gray_rgb":   (0,   500, 0),
        "dark_rgb":       (0,   30,  0),
        "border_fg": curses.COLOR_GREEN,
        "num_colors": {
            1: curses.COLOR_GREEN,  2: curses.COLOR_GREEN,
            3: curses.COLOR_GREEN,  4: curses.COLOR_GREEN,
            5: curses.COLOR_GREEN,  6: curses.COLOR_GREEN,
            7: curses.COLOR_GREEN,  8: curses.COLOR_GREEN,
        },
    },
    "Ocean": {
        "unrevealed_rgb": (100, 200, 300),
        "revealed_rgb":   (30,  80, 150),
        "mid_gray_rgb":   (150, 280, 400),
        "dark_rgb":       (20,  50, 100),
        "border_fg": curses.COLOR_CYAN,
        "num_colors": {
            1: curses.COLOR_WHITE,   2: curses.COLOR_CYAN,
            3: curses.COLOR_YELLOW,  4: curses.COLOR_MAGENTA,
            5: curses.COLOR_GREEN,   6: curses.COLOR_BLUE,
            7: curses.COLOR_WHITE,   8: curses.COLOR_WHITE,
        },
    },
}

THEME_NAMES = list(THEMES.keys())

# ── Config ────────────────────────────────────────────────────

DEFAULT_CONFIG = {"theme": "Classic", "show_coords": True, "zoom": 0}


def normalize_config(cfg):
    if not isinstance(cfg, dict):
        cfg = {}

    theme = cfg.get("theme", DEFAULT_CONFIG["theme"])
    if theme not in THEMES:
        theme = DEFAULT_CONFIG["theme"]

    show_coords = cfg.get("show_coords", DEFAULT_CONFIG["show_coords"])
    if not isinstance(show_coords, bool):
        show_coords = DEFAULT_CONFIG["show_coords"]

    zoom = cfg.get("zoom", DEFAULT_CONFIG["zoom"])
    if not isinstance(zoom, int):
        zoom = DEFAULT_CONFIG["zoom"]
    zoom = max(-1, min(2, zoom))

    return {"theme": theme, "show_coords": show_coords, "zoom": zoom}


def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return normalize_config(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Game Logic ────────────────────────────────────────────────

class Minesweeper:
    def __init__(self, rows=16, cols=30, mines=99):
        if rows <= 0 or cols <= 0:
            raise ValueError("rows and cols must be positive")
        max_mines = rows * cols - 1
        if mines < 0 or mines > max_mines:
            raise ValueError(f"mines must be between 0 and {max_mines}")

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
        self.cursor_trail = {}

    def place_mines(self, safe_r, safe_c):
        safe = set()
        for dr in range(-1, 2):
            for dc in range(-1, 2):
                safe.add((safe_r + dr, safe_c + dc))

        positions = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in safe]
        if self.mines > len(positions):
            safe = {(safe_r, safe_c)}
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

    def move_cursor(self, dr, dc):
        old = (self.cursor_r, self.cursor_c)
        self.cursor_r = (self.cursor_r + dr) % self.rows
        self.cursor_c = (self.cursor_c + dc) % self.cols
        self.cursor_trail[old] = time.time()

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


# ── Scores ────────────────────────────────────────────────────

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


# ── Colors ────────────────────────────────────────────────────

current_theme = "Classic"

def init_colors(theme_name="Classic"):
    global current_theme
    current_theme = theme_name
    theme = THEMES[theme_name]

    curses.start_color()
    curses.use_default_colors()

    if curses.can_change_color():
        curses.init_color(20, *theme["unrevealed_rgb"])
        curses.init_color(21, 700, 700, 700)
        curses.init_color(22, *theme["revealed_rgb"])
        curses.init_color(23, *theme["mid_gray_rgb"])
        curses.init_color(24, *theme["dark_rgb"])
        unrevealed_bg = 20
        revealed_bg = 22
        mid_gray = 23
        dark_bg = 24
    else:
        unrevealed_bg = curses.COLOR_WHITE
        revealed_bg = curses.COLOR_BLACK
        mid_gray = curses.COLOR_WHITE
        dark_bg = curses.COLOR_BLACK

    nc = theme["num_colors"]
    for i in range(1, 9):
        curses.init_pair(i, nc[i], revealed_bg)

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

    border_fg = theme.get("border_fg") or mid_gray
    curses.init_pair(20, border_fg, -1)
    curses.init_pair(21, curses.COLOR_YELLOW, -1)
    curses.init_pair(22, curses.COLOR_CYAN, -1)

    curses.init_pair(23, curses.COLOR_YELLOW, unrevealed_bg)
    curses.init_pair(24, curses.COLOR_RED, dark_bg)
    curses.init_pair(25, curses.COLOR_GREEN, revealed_bg)
    curses.init_pair(26, curses.COLOR_YELLOW, -1)
    curses.init_pair(27, mid_gray, -1)
    curses.init_pair(28, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(29, curses.COLOR_CYAN, -1)

    # cursor trail: 3 fade levels
    if curses.can_change_color():
        curses.init_color(30, 0, 600, 600)   # bright trail
        curses.init_color(31, 0, 400, 400)   # mid trail
        curses.init_color(32, 0, 200, 200)   # dim trail
        curses.init_pair(30, 30, unrevealed_bg)
        curses.init_pair(31, 31, unrevealed_bg)
        curses.init_pair(32, 32, unrevealed_bg)
        curses.init_pair(33, 30, revealed_bg)
        curses.init_pair(34, 31, revealed_bg)
        curses.init_pair(35, 32, revealed_bg)
    else:
        curses.init_pair(30, curses.COLOR_CYAN, -1)
        curses.init_pair(31, curses.COLOR_CYAN, -1)
        curses.init_pair(32, curses.COLOR_CYAN, -1)
        curses.init_pair(33, curses.COLOR_CYAN, -1)
        curses.init_pair(34, curses.COLOR_CYAN, -1)
        curses.init_pair(35, curses.COLOR_CYAN, -1)

    # coord label color
    curses.init_pair(36, mid_gray, -1)


# ── Drawing ───────────────────────────────────────────────────

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


def get_trail_attr(game, r, c):
    now = time.time()
    if (r, c) not in game.cursor_trail:
        return None
    age = now - game.cursor_trail[(r, c)]
    if age > 0.9:
        del game.cursor_trail[(r, c)]
        return None
    is_rev = game.revealed[r][c]
    base = 33 if is_rev else 30
    if age < 0.3:
        return curses.color_pair(base)
    elif age < 0.6:
        return curses.color_pair(base + 1)
    else:
        return curses.color_pair(base + 2)


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
    elif game.game_over and game.board[r][c] == -1 and not getattr(game, "animating_explosion", False):
        return MINE_CH, curses.color_pair(13)
    else:
        return UNREVEALED, curses.color_pair(10)


def draw_board(stdscr, game, col_offset, row_offset, board_w, anim_cells=None, show_coords=True, cell_w=3):
    border_attr = curses.color_pair(20)
    coord_attr = curses.color_pair(36)

    cw = cell_w + 1

    # column numbers
    if show_coords:
        for c in range(game.cols):
            label = f"{c + 1:>{cell_w}}"
            x = col_offset + 1 + c * cw
            sa(stdscr, row_offset - 2, x, label[:cell_w], coord_attr)

    # top border
    seg = "─" * cell_w
    sa(stdscr, row_offset - 1, col_offset, make_hline(game.cols, "┌", "┬", "┐", seg), border_attr)

    for r in range(game.rows):
        y = row_offset + r * 2

        # row number
        if show_coords:
            label = f"{r + 1:>2}"
            sa(stdscr, y, col_offset - 3, label, coord_attr)

        sa(stdscr, y, col_offset, "│", border_attr)
        for c in range(game.cols):
            x = col_offset + 1 + c * cw
            is_cursor = (r == game.cursor_r and c == game.cursor_c)

            ch, attr = get_cell_display(game, r, c, anim_cells)

            # apply cursor trail glow
            if not is_cursor and not game.game_over:
                trail = get_trail_attr(game, r, c)
                if trail is not None and not game.revealed[r][c] and not game.flagged[r][c] and not game.question[r][c]:
                    ch = " ░ " if cell_w == 3 else (" ░░ " if cell_w == 4 else "░░")
                    attr = trail

            if is_cursor and not game.game_over:
                if game.revealed[r][c]:
                    val = game.board[r][c]
                    if cell_w == 2:
                        ch = f"{val}>" if val > 0 else "> "
                    elif cell_w == 4:
                        ch = f"> {val}<" if val > 0 else ">  <"
                    else:
                        ch = f">{val}<" if val > 0 else "> <"
                elif game.flagged[r][c]:
                    ch = ">⚑<" if cell_w == 3 else (">⚑ <" if cell_w == 4 else "⚑>")
                elif game.question[r][c]:
                    ch = ">?<" if cell_w == 3 else ("> ?<" if cell_w == 4 else "?>")
                else:
                    ch = ">█<" if cell_w == 3 else (">██<" if cell_w == 4 else "█>")
                attr = curses.color_pair(15) | curses.A_BOLD

            # adjust content width
            if len(ch) > cell_w:
                ch = ch[:cell_w]
            elif len(ch) < cell_w:
                ch = ch.center(cell_w)

            sa(stdscr, y, x, ch, attr)
            sa(stdscr, y, x + cell_w, "│", border_attr)

        if r < game.rows - 1:
            sa(stdscr, y + 1, col_offset, make_hline(game.cols, "├", "┼", "┤", seg), border_attr)

    bot_y = row_offset + (game.rows - 1) * 2 + 1
    sa(stdscr, bot_y, col_offset, make_hline(game.cols, "└", "┴", "┘", seg), border_attr)
    return bot_y


def draw_progress_bar(stdscr, y, x, width, pct, attr_fill, attr_empty):
    filled = int(width * pct / 100)
    sa(stdscr, y, x, "▓" * filled, attr_fill)
    sa(stdscr, y, x + filled, "░" * (width - filled), attr_empty)


def draw(stdscr, game, anim_cells=None, difficulty_name="", show_coords=True, cell_w=3):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    cw = cell_w + 1
    board_w = game.cols * cw + 1
    coord_margin = 4 if show_coords else 0
    col_offset = max(coord_margin, (w - board_w) // 2)
    row_offset = 5 if show_coords else 4

    # header
    header_y = row_offset - (4 if show_coords else 3)
    mine_str = f" ⚑ {game.flags_remaining:3d}"
    time_str = f" ⏱ {game.elapsed:3d}s"
    sa(stdscr, header_y, col_offset + 1, mine_str, curses.color_pair(21) | curses.A_BOLD)
    sa(stdscr, header_y, col_offset + board_w - len(time_str) - 1, time_str, curses.color_pair(22) | curses.A_BOLD)

    if difficulty_name:
        diff_label = f"[{difficulty_name}]"
        sa(stdscr, header_y, col_offset + (board_w - len(diff_label)) // 2, diff_label, curses.A_DIM)

    if not game.first_move:
        face = " ☺ " if not game.game_over else (" ☻ " if game.won else " ☹ ")
        face_x = col_offset + (board_w - 3) // 2
        face_attr = curses.color_pair(17 if game.won else (18 if game.game_over else 19)) | curses.A_BOLD
        sa(stdscr, header_y, face_x, face, face_attr)

    # progress bar
    prog_y = header_y + 1
    bar_w = min(board_w - 2, 40)
    bar_x = col_offset + (board_w - bar_w - 6) // 2
    pct = game.progress
    sa(stdscr, prog_y, bar_x, f"{pct:3d}% ", curses.color_pair(22))
    draw_progress_bar(stdscr, prog_y, bar_x + 5, bar_w, pct,
                      curses.color_pair(26), curses.color_pair(27))

    # board
    bot_y = draw_board(stdscr, game, col_offset, row_offset, board_w, anim_cells, show_coords, cell_w)

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

        restart_msg = "[R] Restart  [N] New  [S] Scores  [Q] Quit"
        sa(stdscr, status_y + 2, col_offset + (board_w - len(restart_msg)) // 2, restart_msg, curses.A_DIM)
    else:
        line1 = "[Space] Reveal  [F] Flag  [M] ?-Cycle  [C] Chord"
        line2 = "[T] Theme  [G] Coords  [Z/X] Zoom  [R] Restart  [Q] Quit"
        sa(stdscr, status_y, col_offset + (board_w - len(line1)) // 2, line1, curses.A_DIM)
        sa(stdscr, status_y + 1, col_offset + (board_w - len(line2)) // 2, line2, curses.A_DIM)

    # theme label in bottom-right
    theme_label = f"Theme: {current_theme}"
    sa(stdscr, status_y + 3, col_offset + (board_w - len(theme_label)) // 2, theme_label, curses.color_pair(29))

    stdscr.refresh()


# ── Animations ────────────────────────────────────────────────

def animate_reveal(stdscr, game, newly_revealed, difficulty_name, show_coords, cell_w):
    if not newly_revealed or len(newly_revealed) < 3:
        return

    batch_size = max(1, len(newly_revealed) // 8)
    for i in range(0, len(newly_revealed), batch_size):
        batch = set(newly_revealed[i:i + batch_size])
        draw(stdscr, game, anim_cells=batch, difficulty_name=difficulty_name, show_coords=show_coords, cell_w=cell_w)
        time.sleep(0.02)
    draw(stdscr, game, difficulty_name=difficulty_name, show_coords=show_coords, cell_w=cell_w)


def board_layout(stdscr, game, show_coords=True, cell_w=3):
    _, w = stdscr.getmaxyx()
    cw = cell_w + 1
    board_w = game.cols * cw + 1
    coord_margin = 4 if show_coords else 0
    col_offset = max(coord_margin, (w - board_w) // 2)
    row_offset = 5 if show_coords else 4
    return col_offset, row_offset, board_w, cw


def cell_position(stdscr, game, r, c, show_coords=True, cell_w=3):
    col_offset, row_offset, _, cw = board_layout(stdscr, game, show_coords, cell_w)
    return row_offset + r * 2, col_offset + 1 + c * cw


def draw_explosion_cells(stdscr, game, cells, text, attr, show_coords, cell_w):
    for r, c in cells:
        y, x = cell_position(stdscr, game, r, c, show_coords, cell_w)
        label = text[:cell_w].center(cell_w)
        sa(stdscr, y, x, label, attr)


def animate_explosion(stdscr, game, difficulty_name, show_coords, cell_w):
    if not game.exploded:
        return

    er, ec = game.exploded
    game.animating_explosion = True
    mines_by_distance = []
    max_dist = 0
    for r in range(game.rows):
        for c in range(game.cols):
            dist = abs(r - er) + abs(c - ec)
            max_dist = max(max_dist, dist)
            if game.board[r][c] == -1:
                mines_by_distance.append((dist, r, c))
    mines_by_distance.sort()

    impact_cells = [
        (er + dr, ec + dc)
        for dr in range(-1, 2)
        for dc in range(-1, 2)
        if 0 <= er + dr < game.rows and 0 <= ec + dc < game.cols
    ]

    # Impact flash: make the blast feel immediate before the wave expands.
    for text, pair, delay in (("!!!", 28, 0.08), ("***", 21, 0.06), ("!!!", 18, 0.05)):
        draw(stdscr, game, difficulty_name=difficulty_name, show_coords=show_coords, cell_w=cell_w)
        draw_explosion_cells(stdscr, game, impact_cells, text, curses.color_pair(pair) | curses.A_BOLD, show_coords, cell_w)
        stdscr.refresh()
        time.sleep(delay)

    revealed_mine_index = 0
    for dist in range(max_dist + 1):
        while revealed_mine_index < len(mines_by_distance) and mines_by_distance[revealed_mine_index][0] <= dist:
            _, r, c = mines_by_distance[revealed_mine_index]
            if (r, c) != game.exploded:
                game.revealed[r][c] = True
            revealed_mine_index += 1

        ring = [
            (r, c)
            for r in range(game.rows)
            for c in range(game.cols)
            if abs(r - er) + abs(c - ec) == dist
        ]
        draw(stdscr, game, difficulty_name=difficulty_name, show_coords=show_coords, cell_w=cell_w)
        if ring:
            wave_text = "▒" * cell_w if dist % 2 else "▓" * cell_w
            wave_pair = 21 if dist % 2 else 28
            draw_explosion_cells(stdscr, game, ring, wave_text, curses.color_pair(wave_pair) | curses.A_BOLD, show_coords, cell_w)
            stdscr.refresh()
        delay = 0.055 if dist < 4 else 0.025
        time.sleep(delay)

    game.animating_explosion = False

    # Final ember pulse over every mine so the finished board still feels animated.
    mine_cells = [(r, c) for _, r, c in mines_by_distance]
    for text, pair, delay in (("✹", 18, 0.08), ("*", 21, 0.07), ("✹", 13, 0.06)):
        draw(stdscr, game, difficulty_name=difficulty_name, show_coords=show_coords, cell_w=cell_w)
        draw_explosion_cells(stdscr, game, mine_cells, text, curses.color_pair(pair) | curses.A_BOLD, show_coords, cell_w)
        stdscr.refresh()
        time.sleep(delay)


def animate_win(stdscr, game, difficulty_name, show_coords, cell_w):
    h, w = stdscr.getmaxyx()
    cw = cell_w + 1
    board_w = game.cols * cw + 1
    coord_margin = 4 if show_coords else 0
    col_offset = max(coord_margin, (w - board_w) // 2)

    sparkle_chars = ["✦", "✧", "★", "☆", "·", "◆", "◇", "●"]
    for frame in range(18):
        draw(stdscr, game, difficulty_name=difficulty_name, show_coords=show_coords, cell_w=cell_w)
        n_sparkles = 4 + frame // 3
        for _ in range(n_sparkles):
            sy = random.randint(0, h - 1)
            sx = random.randint(col_offset, min(col_offset + board_w - 1, w - 2))
            ch = random.choice(sparkle_chars)
            color = random.choice([17, 21, 22, 29])
            sa(stdscr, sy, sx, ch, curses.color_pair(color) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(0.10)


# ── Screens ───────────────────────────────────────────────────

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
                    medal = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}."
                    rank = f"  {medal} {entry['time']:4d}s   {entry['date']}  "
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


def select_difficulty(stdscr, cfg):
    curses.curs_set(0)
    init_colors(cfg.get("theme", "Classic"))
    selected = 0

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        title_y = h // 2 - 9
        for i, line in enumerate(TITLE_ART):
            cx = max(0, (w - len(line)) // 2)
            sa(stdscr, title_y + i, cx, line, curses.color_pair(22) | curses.A_BOLD)

        # subtitle
        sub = f"Theme: {cfg.get('theme', 'Classic')}"
        sa(stdscr, title_y + 5, max(0, (w - len(sub)) // 2), sub, curses.color_pair(29))

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

        hint = "↑↓ Select   Enter Start   T Theme   S Scores   Q Quit"
        sa(stdscr, h // 2 + 9, max(0, (w - len(hint)) // 2), hint, curses.A_DIM)

        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            selected = (selected - 1) % len(DIFFICULTIES)
        elif key in (curses.KEY_DOWN, ord('j')):
            selected = (selected + 1) % len(DIFFICULTIES)
        elif key in (ord('t'), ord('T')):
            idx = THEME_NAMES.index(cfg.get("theme", "Classic"))
            idx = (idx + 1) % len(THEME_NAMES)
            cfg["theme"] = THEME_NAMES[idx]
            save_config(cfg)
            init_colors(cfg["theme"])
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


# ── Main ──────────────────────────────────────────────────────

def main(stdscr):
    curses.curs_set(0)
    sys.setrecursionlimit(10000)

    cfg = load_config()
    init_colors(cfg.get("theme", "Classic"))

    result = select_difficulty(stdscr, cfg)
    if result[0] is None:
        return
    rows, cols, mines, diff_name = result

    game = Minesweeper(rows, cols, mines)
    stdscr.nodelay(True)
    stdscr.timeout(100)

    show_coords = cfg.get("show_coords", True)
    zoom = cfg.get("zoom", 0)
    cell_w = max(2, min(5, CELL_W + zoom))

    while True:
        draw(stdscr, game, difficulty_name=diff_name, show_coords=show_coords, cell_w=cell_w)

        key = stdscr.getch()
        if key == -1:
            continue

        if key in (ord('q'), ord('Q')):
            break
        elif key in (ord('n'), ord('N')):
            stdscr.nodelay(False)
            stdscr.timeout(-1)
            result = select_difficulty(stdscr, cfg)
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

        # visual toggles (work during gameplay)
        if key in (ord('t'), ord('T')):
            idx = THEME_NAMES.index(cfg.get("theme", "Classic"))
            idx = (idx + 1) % len(THEME_NAMES)
            cfg["theme"] = THEME_NAMES[idx]
            save_config(cfg)
            init_colors(cfg["theme"])
            continue
        elif key in (ord('g'), ord('G')):
            show_coords = not show_coords
            cfg["show_coords"] = show_coords
            save_config(cfg)
            continue
        elif key in (ord('z'), ord('Z')):
            cell_w = min(5, cell_w + 1)
            cfg["zoom"] = cell_w - CELL_W
            save_config(cfg)
            continue
        elif key in (ord('x'), ord('X')):
            cell_w = max(2, cell_w - 1)
            cfg["zoom"] = cell_w - CELL_W
            save_config(cfg)
            continue

        if game.game_over:
            continue

        if key in (curses.KEY_UP, ord('k'), ord('w')):
            game.move_cursor(-1, 0)
        elif key in (curses.KEY_DOWN, ord('j'), ord('s')):
            game.move_cursor(1, 0)
        elif key in (curses.KEY_LEFT, ord('h'), ord('a')):
            game.move_cursor(0, -1)
        elif key in (curses.KEY_RIGHT, ord('l'), ord('d')):
            game.move_cursor(0, 1)
        elif key == ord(' '):
            stdscr.nodelay(False)
            newly = game.reveal(game.cursor_r, game.cursor_c)
            if game.game_over and not game.won:
                animate_explosion(stdscr, game, diff_name, show_coords, cell_w)
            elif newly:
                animate_reveal(stdscr, game, newly, diff_name, show_coords, cell_w)
            if game.won:
                if diff_name != "Custom":
                    save_score(diff_name, game.elapsed)
                animate_win(stdscr, game, diff_name, show_coords, cell_w)
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
                animate_explosion(stdscr, game, diff_name, show_coords, cell_w)
            elif newly:
                animate_reveal(stdscr, game, newly, diff_name, show_coords, cell_w)
            if game.won:
                if diff_name != "Custom":
                    save_score(diff_name, game.elapsed)
                animate_win(stdscr, game, diff_name, show_coords, cell_w)
            stdscr.nodelay(True)
            stdscr.timeout(100)


if __name__ == "__main__":
    curses.wrapper(main)
