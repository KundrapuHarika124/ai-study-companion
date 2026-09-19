from app.services.mastery import next_mastery, PRIOR


def test_first_evidence_moves_strongly():
    assert next_mastery(None, 0, 1.0, "medium", "mcq") > 0.9
    assert next_mastery(None, 0, 0.0, "medium", "mcq") < 0.1


def test_step_shrinks_with_evidence():
    big = next_mastery(0.5, 1, 1.0, "medium", "mcq") - 0.5
    small = next_mastery(0.5, 20, 1.0, "medium", "mcq") - 0.5
    assert big > small > 0


def test_hard_correct_lifts_more_than_easy_correct():
    assert next_mastery(0.5, 5, 1.0, "hard", "mcq") > next_mastery(0.5, 5, 1.0, "easy", "mcq")


def test_easy_wrong_hurts_more_than_hard_wrong():
    assert next_mastery(0.6, 5, 0.0, "easy", "mcq") < next_mastery(0.6, 5, 0.0, "hard", "mcq")


def test_bounded():
    assert 0.0 <= next_mastery(0.99, 3, 1.0, "hard", "open") <= 1.0
    assert 0.0 <= next_mastery(0.01, 3, 0.0, "easy", "open") <= 1.0


def test_prior_is_neutral():
    assert PRIOR == 0.5
