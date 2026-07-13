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


def test_proficiency_reward_ema(tmp_path):
    srs = SRS(tmp_path / "cards.json")
    srs.add("ephemeral", "short-lived")
    today = date(2026, 7, 9)
    c = srs.cards["ephemeral"]
    assert c.prof == 0.5                        # neutral prior

    srs.review("ephemeral", grade=1, today=today)   # Again
    p_fail = c.prof
    assert p_fail < 0.5                             # reward 0 pulls it down
    assert c.ease < 2.5                             # failing dents ease too

    srs.review("ephemeral", grade=4, today=today)   # Good
    assert p_fail < c.prof < 0.8                    # recovers, but history lingers

    # a word that was always Good ends up more proficient than one that lapsed once
    srs.add("kudos", "praise")
    srs.review("kudos", grade=4, today=today)
    assert srs.cards["kudos"].prof > c.prof


def test_proficiency_scales_interval(tmp_path):
    srs = SRS(tmp_path / "cards.json")
    today = date(2026, 7, 9)
    for term, grades in [("steady", [4, 4, 4, 4]), ("shaky", [1, 4, 4, 4, 4])]:
        srs.add(term, "x")
        for g in grades:
            srs.review(term, grade=g, today=today)
    # same last-3-passes shape, but the early lapse leaves "shaky" on shorter intervals
    assert srs.cards["shaky"].interval < srs.cards["steady"].interval


def test_old_state_without_prof_loads(tmp_path):
    p = tmp_path / "cards.json"
    p.write_text('[{"term": "legacy", "definition": "d", "ease": 2.5, '
                 '"interval": 6, "reps": 2, "due": "2026-07-01"}]', encoding="utf-8")
    srs = SRS(p)                                     # pre-prof JSON must still load
    assert srs.cards["legacy"].prof == 0.5
