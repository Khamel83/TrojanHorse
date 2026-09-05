from __future__ import annotations

import json

from work_corpus.db import connect, record_evidence, record_source_version, upsert_source_record
from work_corpus.entities import (
    EntityResolver,
    add_alias,
    create_entity,
    record_scope_proposal,
    resolve_mention,
    select_canonical_name,
)


def _evidence(tmp_path):
    con = connect(tmp_path / "state.sqlite")
    con.execute(
        """
        INSERT INTO source_root (root_key, relative_path, source_system, precedence)
        VALUES ('synthetic', 'synthetic', 'synthetic', 1)
        """
    )
    source_id = upsert_source_record(
        con,
        root_key="synthetic",
        relative_path="synthetic/names.md",
        source_system="synthetic",
        kind="document",
        scope="Work",
        sensitivity="internal_review",
    )
    version_id = record_source_version(con, source_id, 12, 1, "a" * 64)
    evidence_id = record_evidence(
        con,
        version_id,
        "document",
        "corpus/names.md",
        "b" * 64,
        "derived",
        derived_text="synthetic names",
    )
    con.commit()
    return con, source_id, evidence_id


def test_stable_entity_id_and_exact_alias_preserve_original_mention(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        first = create_entity(con, "project", "project-alpha", "Alpha")
        second = create_entity(con, "project", "project-alpha", "Alpha renamed")
        add_alias(
            con,
            first,
            "ALPHA",
            source_system="synthetic",
            evidence_id=evidence_id,
            rule="dictionary",
            review_status="valid",
        )

        match = resolve_mention(
            con,
            " ALPHA ",
            evidence_id=evidence_id,
            source_id=source_id,
            location="line:1",
            source_system="synthetic",
        )
        row = con.execute(
            "SELECT original_mention, rule, entity_id FROM entity_mention"
        ).fetchone()
    finally:
        con.close()

    assert first == second
    assert match.entity_id == first
    assert match.rule == "exact_alias"
    assert row["original_mention"] == " ALPHA "
    assert row["rule"] == "exact_alias"


def test_regex_normalization_and_source_specific_alias(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        entity_id = create_entity(con, "organization", "org-acme", "Acme, Inc.")
        add_alias(
            con,
            entity_id,
            "ACME, INC.",
            evidence_id=evidence_id,
            review_status="valid",
        )
        regex_match = resolve_mention(
            con,
            "acme inc",
            evidence_id=evidence_id,
            source_id=source_id,
            location="line:2",
        )
        add_alias(
            con,
            entity_id,
            "acct-042",
            source_system="synthetic",
            evidence_id=evidence_id,
            rule="source_identifier",
            review_status="valid",
        )
        identifier_match = resolve_mention(
            con,
            "Account 42",
            evidence_id=evidence_id,
            source_id=source_id,
            location="line:3",
            source_system="synthetic",
            source_identifier="acct-042",
        )
    finally:
        con.close()

    assert regex_match.entity_id == entity_id
    assert regex_match.rule == "normalized_alias"
    assert identifier_match.entity_id == entity_id
    assert identifier_match.rule == "source_identifier"


def test_frequency_can_select_only_a_valid_name_not_a_frequent_typo(tmp_path):
    con, _source_id, evidence_id = _evidence(tmp_path)
    try:
        entity_id = create_entity(con, "project", "project-beta", "Beta")
        add_alias(
            con,
            entity_id,
            "Beta Team",
            evidence_id=evidence_id,
            review_status="valid",
        )
        add_alias(
            con,
            entity_id,
            "Btea Team",
            evidence_id=evidence_id,
            review_status="pending",
        )
        selected = select_canonical_name(
            con,
            entity_id,
            {"Btea Team": 100, "Beta Team": 7, "Beta": 1},
            apply=True,
        )
        row = con.execute(
            "SELECT canonical_name FROM entity WHERE entity_id=?", (entity_id,)
        ).fetchone()
    finally:
        con.close()

    assert selected == "Beta Team"
    assert row["canonical_name"] == "Beta Team"


def test_collision_stays_separate_and_creates_contextual_review(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        one = create_entity(con, "person", "person-one", "Jordan Lee")
        two = create_entity(con, "person", "person-two", "Jordan Lee")
        for entity_id in (one, two):
            add_alias(
                con,
                entity_id,
                "Jordan",
                evidence_id=evidence_id,
                review_status="valid",
            )
        match = resolve_mention(
            con,
            "Jordan",
            evidence_id=evidence_id,
            source_id=source_id,
            location="meeting:1",
            context={"organization": "Acme", "role": "reviewer"},
        )
        review = con.execute(
            "SELECT issue_type, evidence_id, proposed_result_json FROM review_item"
        ).fetchone()
        entities = con.execute("SELECT COUNT(*) AS count FROM entity").fetchone()["count"]
    finally:
        con.close()

    proposal = json.loads(review["proposed_result_json"])
    assert match.entity_id is None
    assert match.status == "review"
    assert match.rule == "collision_review"
    assert set(proposal["candidate_entity_ids"]) == {one, two}
    assert proposal["context"]["role"] == "reviewer"
    assert review["issue_type"] == "entity_collision"
    assert review["evidence_id"] == evidence_id
    assert entities == 2


def test_former_name_alias_remains_linked_and_scope_review_is_provenanced(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        entity_id = create_entity(con, "organization", "org-legacy", "Current Org")
        add_alias(
            con,
            entity_id,
            "Former Org",
            evidence_id=evidence_id,
            valid_from="2018-01-01",
            valid_to="2022-12-31",
            rule="former_name",
            review_status="valid",
        )
        match = resolve_mention(
            con,
            "Former Org",
            evidence_id=evidence_id,
            source_id=source_id,
            location="line:4",
        )
        review_id = record_scope_proposal(
            con,
            source_id,
            "Mixed",
            evidence_id=evidence_id,
            sensitivity="internal_review",
            reason="synthetic mixed source",
        )
        review = con.execute(
            "SELECT issue_type, evidence_id, status FROM review_item WHERE review_id=?",
            (review_id,),
        ).fetchone()
    finally:
        con.close()

    assert match.entity_id == entity_id
    assert match.rule == "exact_alias"
    assert review["issue_type"] == "scope_review"
    assert review["evidence_id"] == evidence_id
    assert review["status"] == "pending"


def test_clear_work_scope_is_accepted_without_a_review_item(tmp_path):
    con, source_id, evidence_id = _evidence(tmp_path)
    try:
        review_id = record_scope_proposal(
            con,
            source_id,
            "Work",
            evidence_id=evidence_id,
            sensitivity="internal_review",
            reason="approved work root",
        )
        count = con.execute("SELECT COUNT(*) FROM review_item").fetchone()[0]
    finally:
        con.close()

    assert review_id is None
    assert count == 0
