from datetime import date, timedelta
from prep_core import SRS


def test_srs_schedules_and_persists(tmp_path):
    srs = SRS(tmp_path / "cards.json")
    srs.add("ubiquitous", "present everywhere")
    today = date(2026, 7, 9)

    assert len(srs.due_cards(today)) == 1  # never-reviewed card is due

    srs.review("ubiquitous", grade=5, today=today)
    c = srs.cards["ubiquitous"]
    assert c.reps == 1 and c.interval == 1
    assert c.due == (today + timedelta(days=1)).isoformat()
    assert srs.due_cards(today) == []      # not due again today

    srs.save()
    reloaded = SRS(tmp_path / "cards.json")
    assert reloaded.cards["ubiquitous"].reps == 1


def test_failed_card_resets(tmp_path):
    srs = SRS(tmp_path / "cards.json")
    srs.add("obfuscate", "to make unclear")
    today = date(2026, 7, 9)
    srs.review("obfuscate", grade=5, today=today)
    srs.review("obfuscate", grade=1, today=today)  # forgot it
    assert srs.cards["obfuscate"].reps == 0
    assert srs.cards["obfuscate"].interval == 1
