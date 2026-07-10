from psn.library_utils import (
    alias_context_by_siblings,
    build_concept_siblings,
    dedupe_library_by_concept,
    enrich_purchased_concept_ids,
    expand_concept_sibling_skus,
)


def test_build_concept_siblings():
    played = [
        {
            "titleId": "CUSA37191_00",
            "concept": {"id": 123, "titleIds": ["CUSA37191_00", "PPSA10609_00"]},
        }
    ]
    siblings = build_concept_siblings(played)
    assert siblings["CUSA37191_00"] == ["PPSA10609_00"]
    assert siblings["PPSA10609_00"] == ["CUSA37191_00"]


def test_dedupe_library_by_concept_prefers_ppsa():
    entries = [
        {"titleId": "CUSA37191_00", "name": "Pursuit Force", "conceptId": 123},
        {"titleId": "PPSA10609_00", "name": "Pursuit Force", "conceptId": 123},
    ]
    deduped = dedupe_library_by_concept(entries)
    assert len(deduped) == 1
    assert deduped[0]["titleId"] == "PPSA10609_00"


def test_expand_concept_sibling_skus():
    entries = [{"titleId": "PPSA09955_00", "name": "Bluey", "conceptId": "999"}]
    siblings = {"PPSA09955_00": ["CUSA36463_00"], "CUSA36463_00": ["PPSA09955_00"]}
    expanded = expand_concept_sibling_skus(entries, siblings)
    assert {entry["titleId"] for entry in expanded} == {
        "PPSA09955_00",
        "CUSA36463_00",
    }


def test_expand_concept_sibling_skus_appends_siblings_after_real_entries():
    # Galaxy ingests release keys in order, so real library entries must all
    # come before any expanded sibling SKUs.
    entries = [
        {"titleId": "PPSA00001_00", "name": "Game A", "conceptId": "1"},
        {"titleId": "PPSA00002_00", "name": "Game B", "conceptId": "2"},
    ]
    siblings = {
        "PPSA00001_00": ["CUSA00001_00"],
        "PPSA00002_00": ["CUSA00002_00"],
    }
    expanded = expand_concept_sibling_skus(entries, siblings)
    assert [entry["titleId"] for entry in expanded[:2]] == [
        "PPSA00001_00",
        "PPSA00002_00",
    ]
    assert len(expanded) == 4


def test_enrich_purchased_concept_ids():
    purchased = [{"titleId": "CUSA36463_00", "name": "Bluey", "source": "purchased"}]
    played = [
        {
            "titleId": "PPSA09955_00",
            "concept": {"id": 999, "titleIds": ["PPSA09955_00", "CUSA36463_00"]},
        }
    ]
    enrich_purchased_concept_ids(purchased, played)
    assert purchased[0]["conceptId"] == "999"


def test_alias_context_by_siblings():
    context = {"PPSA01325_00": ["trophy-a"]}
    siblings = {"PPSA99999_00": ["PPSA01325_00"]}
    alias_context_by_siblings(context, ["PPSA99999_00"], siblings)
    assert context["PPSA99999_00"] == ["trophy-a"]
