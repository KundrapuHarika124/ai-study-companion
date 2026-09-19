from app.services.growth import classify


def h(*vals):
    return [{"mastery": v} for v in vals]


def test_insufficient_evidence():
    assert classify(h(0.5), 0.5, 1) == "insufficient_evidence"


def test_improving():
    assert classify(h(0.4, 0.5, 0.62), 0.62, 3) == "improving"


def test_attention_on_decline_or_low():
    assert classify(h(0.7, 0.6), 0.6, 2) == "attention"
    assert classify(h(0.4, 0.42), 0.42, 2) == "attention"


def test_stable():
    assert classify(h(0.8, 0.82), 0.82, 4) == "stable"
