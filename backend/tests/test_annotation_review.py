"""仅用人工构造的测试记录验证复核流程，不生成真实人工标注。"""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from course_matcher.data import read_pairs, split_families
from course_matcher.review import (
    check_classroom,
    compare,
    finalize,
    prepare,
    read_review,
    write_json,
    write_rows,
)
from sqlalchemy import select
from sqlalchemy.orm import Session
from ta_backend.models import KnowledgeNode


@pytest.fixture
def review_packet(api, tmp_path):
    _, engine = api
    with Session(engine) as session:
        node = session.scalar(select(KnowledgeNode).where(KnowledgeNode.id == "demo-attention"))
        snapshot = {
            "course_id": "demo-nlp",
            "graph_version": 1,
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "aliases": node.aliases,
                    "description": node.description,
                }
            ],
        }
    rows = [
        {
            "id": "q1",
            "question": "怎样计算注意力的加权汇总？",
            "family_id": "f1",
            "node_ids": ["demo-attention"],
            "source": "developer-authored",
            "label_status": "development",
            "rationale": "原标签不应出现在盲审页面",
        },
        {
            "id": "q2",
            "question": "考试安排在哪天？",
            "family_id": "f2",
            "node_ids": [],
            "source": "developer-authored",
            "label_status": "development",
        },
    ]
    source, nodes, output = tmp_path / "source.jsonl", tmp_path / "nodes.json", tmp_path / "packet"
    write_rows(source, rows)
    write_json(nodes, snapshot)
    prepare(source, nodes, Path(engine.url.database), output, "development-test")
    packet = json.loads((output / "packet.json").read_text(encoding="utf-8"))
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for slot, path in [("a", a), ("b", b)]:
        write_rows(
            path,
            [
                {
                    "packet_id": packet["packet_id"],
                    "slot": slot,
                    "id": row["id"],
                    "question": row["question"],
                    "family_id": row["family_id"],
                    "node_ids": row["node_ids"],
                    "no_match": not row["node_ids"],
                    "reviewer": "测试复核" + slot.upper(),
                    "rationale": "离线测试用签核记录",
                    "decision": "confirmed",
                }
                for row in rows
            ],
        )
    return output, packet, a, b


def test_blind_packet_has_sources_but_neither_development_labels_nor_reviews(review_packet):
    output, packet, _, _ = review_packet
    assert all(set(q) == {"id", "question", "family_id"} for q in packet["questions"])
    assert packet["nodes"][0]["evidence"][0]["text"]
    for slot in ("a", "b"):
        html = (output / f"review-{slot}.html").read_text(encoding="utf-8")
        assert "原标签不应出现在盲审页面" not in html
        assert "测试复核" not in html
        payload = json.loads(html.split('type="application/json">')[1].split("</script>")[0])
        assert payload["slot"] == slot
        assert all("node_ids" not in q for q in payload["questions"])


def test_agreement_preserves_authorship_and_development_status(review_packet, tmp_path):
    output, _, a, b = review_packet
    result = tmp_path / "reviewed"
    assert compare(output, a, b, tmp_path / "comparison") == {"questions": 2, "conflicts": 0}
    finalize(output, a, b, result, "reviewed-development-test")
    rows = read_pairs(result / "questions.jsonl")
    assert all(row["label_status"] == "confirmed" for row in rows)
    assert all(row["source"] == "developer-authored" for row in rows)
    assert all(row["review"]["adjudication"] is None for row in rows)
    assert (
        json.loads((result / "dataset.json").read_text(encoding="utf-8"))["data_status"]
        == "development"
    )
    with pytest.raises(FileExistsError):
        finalize(output, a, b, result, "reviewed-development-test")


def test_conflicting_labels_and_families_need_distinct_adjudicator(review_packet, tmp_path):
    output, packet, a, b = review_packet
    rows = read_pairs(b)
    rows[0].update(node_ids=[], no_match=True, family_id="f-new")
    write_rows(b, rows)
    comparison = tmp_path / "comparison"
    assert compare(output, a, b, comparison)["conflicts"] == 1
    assert (comparison / "adjudication.html").exists()
    with pytest.raises(ValueError, match="第三人裁决"):
        finalize(output, a, b, tmp_path / "bad", "reviewed-test")
    decision = {**rows[0], "slot": "adjudication", "reviewer": "测试复核A"}
    adjudication = tmp_path / "adjudication.jsonl"
    write_rows(adjudication, [decision])
    with pytest.raises(ValueError, match="裁决人"):
        finalize(output, a, b, tmp_path / "bad", "reviewed-test", adjudication)
    decision["reviewer"] = "测试裁决C"
    write_rows(adjudication, [decision])
    finalize(output, a, b, tmp_path / "good", "reviewed-test", adjudication)
    final = read_pairs(tmp_path / "good/questions.jsonl")[0]
    assert final["family_id"] == "f-new" and final["node_ids"] == []
    assert final["review"]["a"]["node_ids"] == ["demo-attention"]
    assert final["review"]["adjudication"]["reviewer"] == "测试裁决C"
    assert read_review(packet, a, "a", packet["questions"])


@pytest.mark.parametrize(
    "change",
    [
        {"decision": "pending"},
        {"node_ids": ["foreign-course-node"]},
        {"question": "已被改写"},
        {"node_ids": [], "no_match": False},
        {"reviewer": ""},
        {"rationale": ""},
        {"slot": "b"},
        {"packet_id": "other"},
    ],
)
def test_invalid_or_unconfirmed_reviews_cannot_finalize(review_packet, tmp_path, change):
    output, _, a, b = review_packet
    rows = read_pairs(a)
    rows[0].update(change)
    write_rows(a, rows)
    with pytest.raises(ValueError):
        finalize(output, a, b, tmp_path / "rejected", "reviewed-test")
    assert not (tmp_path / "rejected").exists()


def test_missing_duplicate_and_same_person_reviews_are_rejected(review_packet, tmp_path):
    output, _, a, b = review_packet
    original = read_pairs(a)
    for invalid in [original[:1], original + original[:1]]:
        write_rows(a, invalid)
        with pytest.raises(ValueError):
            compare(output, a, b, tmp_path / "bad")
    write_rows(a, original)
    write_rows(b, [{**r, "reviewer": "测试复核A", "slot": "b"} for r in original])
    with pytest.raises(ValueError, match="不同"):
        compare(output, a, b, tmp_path / "bad")


def classroom_row():
    return {
        "id": "class-01",
        "family_id": "class-family-01",
        "question": "窗口扩大后计数稀疏怎么办？",
        "source": {
            "kind": "classroom",
            "course_id": "nlp-curriculum",
            "session": "测试课次",
            "record_id": "匿名记录01",
            "deidentified": True,
            "used_in_development": False,
        },
    }


def test_classroom_provenance_and_development_overlap_are_checked():
    row = classroom_row()
    excluded = [{"id": "dev-1", "family_id": "dev-family-1", "question": "什么是N元模型？"}]
    check_classroom([row], "nlp-curriculum", excluded)
    for change in [
        {"used_in_development": True},
        {"used_in_development": None},
        {"deidentified": False},
        {"course_id": "other"},
        {"record_id": ""},
    ]:
        bad = deepcopy(row)
        bad["source"].update(change)
        with pytest.raises(ValueError):
            check_classroom([bad], "nlp-curriculum", excluded)
    for change in [{"question": " 什么是 ｎ 元模型? "}, {"family_id": "dev-family-1"}]:
        with pytest.raises(ValueError, match="重复或同家族"):
            check_classroom([{**row, **change}], "nlp-curriculum", excluded)


def test_classroom_results_remain_heldout_after_review(review_packet, tmp_path):
    output, packet, a, b = review_packet
    packet.update(origin="classroom", excluded_families=["known-development-family"])
    write_json(output / "packet.json", packet)
    source = read_pairs(output / "original.jsonl")
    for row in source:
        row["source"] = {**classroom_row()["source"], "course_id": "demo-nlp"}
    write_rows(output / "original.jsonl", source)
    result = tmp_path / "classroom"
    finalize(output, a, b, result, "heldout-test")
    rows = read_pairs(result / "questions.jsonl")
    assert all(r["split_role"] == "heldout" for r in rows)
    with pytest.raises(ValueError, match="独立评价"):
        split_families(rows)
    for file in (a, b):
        write_rows(file, [{**r, "family_id": "known-development-family"} for r in read_pairs(file)])
    with pytest.raises(ValueError, match="家族与开发数据重叠"):
        finalize(output, a, b, tmp_path / "bad", "heldout-test")


def test_classroom_source_cannot_be_prepared_as_ordinary_development(review_packet, tmp_path):
    output, _, _, _ = review_packet
    source = read_pairs(output / "original.jsonl")
    source[0]["source"] = classroom_row()["source"]
    path = tmp_path / "classroom-source.jsonl"
    write_rows(path, source)
    with pytest.raises(ValueError, match="origin classroom"):
        prepare(path, tmp_path / "nodes.json", tmp_path / "unused.db", tmp_path / "bad", "new")
