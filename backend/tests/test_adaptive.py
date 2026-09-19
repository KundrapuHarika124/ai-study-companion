from datetime import timedelta
from app.core.utils import now
from app.services.quiz import select_concept, select_difficulty, select_type


def m(v, n=3, days_ago=1):
    return {"mastery": v, "evidence_count": n, "last_assessed_at": now() - timedelta(days=days_ago)}


def test_prefers_weak_concept():
    mm = {"A": m(0.9), "B": m(0.3), "C": m(0.7)}
    assert select_concept(["A", "B", "C"], mm, [], [], seed=1) == "B"


def test_recent_mistakes_raise_priority():
    mm = {"A": m(0.55), "B": m(0.55)}
    recent = [{"concept": "A", "score": 0.0}, {"concept": "A", "score": 0.0}, {"concept": "B", "score": 1.0}]
    assert select_concept(["A", "B"], mm, recent, [], seed=1) == "A"


def test_unassessed_concept_gets_a_chance():
    mm = {"A": m(0.5)}
    assert select_concept(["A", "NEW"], mm, [], [], seed=1) == "NEW"


def test_session_repetition_penalised():
    mm = {"A": m(0.2), "B": m(0.4)}
    assert select_concept(["A", "B"], mm, [], ["A", "A"], seed=1) == "B"


def test_focus_concept_wins():
    assert select_concept(["A", "B"], {"A": m(0.1)}, [], [], focus="B") == "B"


def test_difficulty_is_not_wrong_easy_correct_hard():
    # low mastery but two correct answers in a row: steps up one level, not straight to hard
    assert select_difficulty(m(0.3), [{"score": 1.0}, {"score": 1.0}]) == "medium"
    # high mastery with two wrong answers: steps down to medium, not straight to easy
    assert select_difficulty(m(0.8), [{"score": 0.0}, {"score": 0.0}]) == "medium"
    # a single wrong answer does not change the band
    assert select_difficulty(m(0.8), [{"score": 0.0}]) == "hard"


def test_open_ended_mixed_in():
    assert select_type(2, "easy", m(0.3)) == "open"
    assert select_type(0, "hard", m(0.7)) == "open"
    assert select_type(0, "easy", m(0.3)) == "mcq"
