import pytest

from minesweeper import Minesweeper, normalize_config


def test_invalid_config_values_fall_back_to_safe_defaults():
    assert normalize_config({"theme": "Missing", "show_coords": "yes", "zoom": 99}) == {
        "theme": "Classic",
        "show_coords": True,
        "zoom": 2,
    }


def test_game_rejects_impossible_mine_counts():
    with pytest.raises(ValueError, match="mines must be between"):
        Minesweeper(2, 2, 4)


def test_first_move_remains_safe_when_too_many_mines_for_full_neighborhood():
    game = Minesweeper(2, 2, 3)
    game.reveal(0, 0)

    assert game.board[0][0] != -1
    assert sum(cell == -1 for row in game.board for cell in row) == 3
