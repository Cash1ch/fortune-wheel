# -*- coding: utf-8 -*-
import random
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import fortune_core as fc
from fortune_core import FortuneState, WheelPhysics


def run_spin(n, seed):
    ph = WheelPhysics(random.Random(seed))
    ph.set_count(n)
    assert ph.start()
    t, pegs, winner = 0.0, 0, None
    while ph.spinning:
        for kind, val in ph.update(1 / 60):
            if kind == "peg":
                pegs += 1
            else:
                winner = val
        t += 1 / 60
        assert t < 60, "колесо не остановилось за 60 с"
    return winner, pegs, t


@pytest.mark.parametrize("n", [1, 2, 3, 8, 24])
def test_spin_terminates_and_winner_valid(n):
    for seed in range(60):
        w, pegs, t = run_spin(n, seed)
        assert 0 <= w < n
        assert t > 1.0                      # не мгновенная остановка


def test_winner_is_roughly_uniform():
    n, counts = 6, [0] * 6
    for seed in range(1500):
        counts[run_spin(n, seed)[0]] += 1
    assert min(counts) > 1500 / n * 0.7, counts
    assert max(counts) < 1500 / n * 1.3, counts


def test_pointer_matches_winner_and_not_on_boundary():
    for seed in range(100):
        ph = WheelPhysics(random.Random(seed)); ph.set_count(8); ph.start()
        while ph.spinning:
            ph.update(1 / 60)
        frac = ((-ph.rot) % 360.0) % ph.sector
        assert 0.3 < frac < ph.sector - 0.3
        assert ph.winner == ph.pointer_index()


def test_rollback_stays_before_peg_when_fixed(monkeypatch):
    monkeypatch.setattr(fc, "FIX_ROLLBACK", True)
    checked = 0
    for seed in range(600):
        ph = WheelPhysics(random.Random(seed)); ph.set_count(8); ph.start()
        stalled = None
        while ph.spinning:
            was = ph.rolling_back
            before = ph.pointer_index()
            ph.update(1 / 60)
            if ph.rolling_back and not was:
                stalled = before
        if stalled is not None:
            checked += 1
            assert ph.winner == stalled
    assert checked > 20


def test_options_limits():
    st = FortuneState()
    assert st.add_option("  ")[0] is False
    for i in range(fc.MAX_OPTIONS):
        assert st.add_option(f"v{i}")[0]
    ok, msg = st.add_option("лишний")
    assert not ok and "Максимум" in msg


def test_elimination_run_ends_with_single_winner_then_restarts():
    st = FortuneState(["a", "b", "c"], elim_on=True)
    rnd = random.Random(1)
    removed = []
    for _ in range(2):
        st.prepare_spin()
        res = st.on_finished(rnd.randrange(len(st.pool)))
        assert res["kind"] == "eliminate"
        removed.append(res["text"])
        out = st.apply_elimination()
    assert out["done"] and out["text"] not in removed
    assert len(set(removed)) == 2
    st.prepare_spin()                       # новый круг со всеми вариантами
    assert len(st.pool) == 3 and not st.run_done


def test_normal_mode_returns_text_of_sector():
    st = FortuneState(["a", "b", "c"])
    assert st.on_finished(1) == {"kind": "win", "text": "b"}


def test_single_option_wins_even_in_elim_mode():
    st = FortuneState(["only"], elim_on=True)
    st.prepare_spin()
    assert st.on_finished(0)["kind"] == "win"
