"""Property-based tests for the assistant's turn slots (fakes only, no network).

``TurnSlots`` is the table that keeps a process from answering more than a set number of
turns at once, and one user from running more than their share. The example tests in
``test_deps.py`` pin single cases; these drive random sequences of takes and returns
against a plain model of who holds what, and check the table after every step.
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from api.assistant import deps

_USERS = [UUID(int=number) for number in range(1, 4)]


class TurnSlotsMachine(RuleBasedStateMachine):
    """Take and give back slots at random, and compare the table with a model of the holders.

    The model is a dict of user id to the number of slots that user holds, kept by the
    machine itself from what each step is known to do.
    """

    def __init__(self) -> None:
        super().__init__()
        self.slots = deps.TurnSlots(max_total=1, max_per_user=1)
        self.held: dict[UUID, int] = {}

    @initialize(max_total=st.integers(1, 6), max_per_user=st.integers(1, 3))
    def build_table(self, max_total: int, max_per_user: int) -> None:
        """Build a table of a random size, so the caps vary from run to run."""
        self.slots = deps.TurnSlots(max_total=max_total, max_per_user=max_per_user)

    @rule(user=st.sampled_from(_USERS))
    def acquire(self, user: UUID) -> None:
        """Ask for a slot: the process cap is checked first, then the user's own."""
        if sum(self.held.values()) >= self.slots.max_total:
            expected = "process"
        elif self.held.get(user, 0) >= self.slots.max_per_user:
            expected = "user"
        else:
            expected = None

        refused_by = self.slots.acquire(user)

        assert refused_by == expected
        if refused_by is None:
            self.held[user] = self.held.get(user, 0) + 1

    @precondition(lambda self: bool(self.held))
    @rule(data=st.data())
    def cancel_a_holder(self, data: st.DataObject) -> None:
        """Give back a slot a user holds, as ``hold_turn_slot`` does when its turn is cancelled."""
        user = data.draw(st.sampled_from(sorted(self.held)))

        self.slots.release(user)

        self.held[user] -= 1
        if self.held[user] == 0:
            del self.held[user]

    @rule(user=st.sampled_from(_USERS))
    def release_a_slot_never_taken(self, user: UUID) -> None:
        """Release for a user who holds nothing: the table stays exactly as it was."""
        if user in self.held:
            return
        before = dict(self.slots.holders)

        self.slots.release(user)

        assert self.slots.holders == before

    @invariant()
    def the_table_agrees_with_the_model_and_the_caps(self) -> None:
        """Every count matches the model, none is zero, and no cap is passed."""
        holders = self.slots.holders
        assert holders == self.held
        assert 0 <= sum(holders.values()) <= self.slots.max_total
        assert all(0 < count <= self.slots.max_per_user for count in holders.values())


TurnSlotsMachine.TestCase.settings = settings(
    max_examples=100, stateful_step_count=40, deadline=None
)
TestTurnSlotsSequences = TurnSlotsMachine.TestCase


class TestHoldTurnSlotUnderCancellation:
    """A turn cancelled while it holds a slot gives that slot back."""

    @pytest.mark.asyncio
    async def test_cancelled_turns_give_back_exactly_their_own_slots(self):
        """
        GIVEN three turns running inside ``hold_turn_slot``, two for one user and one for another
        WHEN the first user's two turns are cancelled, and then the other's
        THEN each cancellation frees only the slots of the cancelled turn, and the table ends empty
        """
        # GIVEN
        slots = deps.TurnSlots(max_total=3, max_per_user=2)
        first, second = MagicMock(id=_USERS[0]), MagicMock(id=_USERS[1])
        entered = asyncio.Event()
        running = 0

        async def turn(user: MagicMock) -> None:
            nonlocal running
            async with asynccontextmanager(deps.hold_turn_slot)(user, slots):
                running += 1
                if running == 3:
                    entered.set()
                await asyncio.sleep(3600)

        first_turns = [asyncio.create_task(turn(first)) for _ in range(2)]
        second_turn = asyncio.create_task(turn(second))
        await asyncio.wait_for(entered.wait(), timeout=5)
        assert slots.holders == {_USERS[0]: 2, _USERS[1]: 1}

        # WHEN/THEN
        for task in first_turns:
            task.cancel()
        await asyncio.gather(*first_turns, return_exceptions=True)
        assert slots.holders == {_USERS[1]: 1}
        second_turn.cancel()
        await asyncio.gather(second_turn, return_exceptions=True)
        assert slots.holders == {}
        assert all(task.cancelled() for task in [*first_turns, second_turn])
