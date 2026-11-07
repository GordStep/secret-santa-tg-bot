from __future__ import annotations

import pytest

from secret_santa.bot.services.derangement import make_derangement


@pytest.mark.parametrize("size", [2, 3, 10, 100])
def test_derangement_is_fixed_point_free_bijection(size: int) -> None:
    user_ids = list(range(1, size + 1))
    for _ in range(25):
        result = make_derangement(user_ids)
        assert set(result) == set(user_ids)
        assert set(result.values()) == set(user_ids)
        assert len(result) == size
        assert all(giver != receiver for giver, receiver in result.items())


def test_derangement_preserves_input() -> None:
    user_ids = [1, 2, 3]
    make_derangement(user_ids)
    assert user_ids == [1, 2, 3]


@pytest.mark.parametrize("user_ids", [[], [1], [1, 1]])
def test_derangement_rejects_invalid_input(user_ids: list[int]) -> None:
    with pytest.raises(ValueError):
        make_derangement(user_ids)
