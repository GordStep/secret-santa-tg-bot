from __future__ import annotations

import random


def make_derangement(user_ids: list[int]) -> dict[int, int]:
    if len(user_ids) < 2:
        raise ValueError("At least two participants are required")
    if len(set(user_ids)) != len(user_ids):
        raise ValueError("Participant IDs must be unique")

    receivers = user_ids.copy()
    for index in range(len(receivers) - 1, 0, -1):
        other_index = random.randrange(index)
        receivers[index], receivers[other_index] = (
            receivers[other_index],
            receivers[index],
        )
    return dict(zip(user_ids, receivers, strict=True))
