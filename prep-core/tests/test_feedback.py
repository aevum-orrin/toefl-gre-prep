from prep_core import FeedbackEngine, Rubric
from prep_core.audio import word_accuracy

RUBRIC = Rubric.from_dict({
    "name": "Test rubric",
    "task_type": "academic_discussion",
    "scale_min": 1,
    "scale_max": 6,
    "criteria": [
        {"key": "content", "name": "Content", "description": "relevance and development"},
        {"key": "language", "name": "Language use", "description": "grammar and vocabulary"},
    ],
})


def test_offline_stub_returns_structured_feedback():
    eng = FeedbackEngine(offline=True)
    fb = eng.score_writing("This is a short essay about technology.", RUBRIC)
    assert fb.offline is True
    assert RUBRIC.scale_min <= fb.band <= RUBRIC.scale_max
    assert set(fb.criteria) == {"content", "language"}
    assert isinstance(fb.top_fixes, list) and fb.top_fixes


def test_word_accuracy():
    assert word_accuracy("the cat sat", "the cat sat") == 1.0
    assert word_accuracy("the cat sat", "the cat") == round(2 / 3, 3)
    assert word_accuracy("", "anything") == 0.0
