from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from ta_backend.models import (
    Chunk,
    Course,
    KnowledgeEdge,
    KnowledgeNode,
    Material,
    NodeEvidence,
    Question,
)

ROOT = "/api/v1/courses/demo-nlp"
COMPARISONS = f"{ROOT}/evidence/comparisons"


@pytest.fixture
def graph_sources(api):
    client, engine = api
    with Session(engine) as session:
        session.add_all(
            [
                Material(id="experiment-material", course_id="demo-nlp", title="实验资料"),
                Material(
                    id="expired-material", course_id="demo-nlp", title="过期资料", active=False
                ),
            ]
        )
        session.flush()
        session.add(
            Chunk(
                id="lexical",
                course_id="demo-nlp",
                material_id="experiment-material",
                locator="词面",
                text="anchor anchor lexical",
                position=0,
            )
        )
        session.add(
            Chunk(
                id="expired",
                course_id="demo-nlp",
                material_id="expired-material",
                locator="旧版",
                text="过期关系依据",
            )
        )
        for i, name in enumerate("abcdef", 1):
            session.add(
                Chunk(
                    id=f"source-{name}",
                    course_id="demo-nlp",
                    material_id="experiment-material",
                    locator=name,
                    text=f"证据{name}，用于解释概念。",
                    position=i,
                )
            )
            session.add(
                KnowledgeNode(
                    id=name,
                    course_id="demo-nlp",
                    name=f"概念{name}",
                    status="candidate" if name == "f" else "confirmed",
                )
            )
        session.flush()
        session.add_all(
            NodeEvidence(course_id="demo-nlp", node_id=n, chunk_id=f"source-{n}") for n in "abcdef"
        )
        for source, target, status, chunk in [
            ("a", "b", "confirmed", "source-a"),
            ("b", "c", "confirmed", "source-b"),
            ("a", "d", "candidate", "source-a"),
            ("a", "e", "confirmed", "expired"),
            ("a", "f", "confirmed", "source-a"),
        ]:
            session.add(
                KnowledgeEdge(
                    id=f"edge-{source}{target}",
                    course_id="demo-nlp",
                    source_id=source,
                    target_id=target,
                    status=status,
                    chunk_id=chunk,
                    relation="uses",
                )
            )
        session.commit()
    return client, engine


def compare(client, **overrides):
    response = client.post(
        COMPARISONS,
        json={
            "question_text": "anchor",
            "node_ids": ["a"],
            "evidence_budget": 2,
            **overrides,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_same_corpus_budget_and_explainable_replacement(graph_sources):
    client, _ = graph_sources
    record = compare(client)
    snapshot = record["snapshot"]
    basic, augmented = snapshot["basic"]["evidence"], snapshot["graph_augmented"]["evidence"]
    assert [e["id"] for e in basic] == ["lexical"]
    assert [e["id"] for e in augmented] == ["source-a", "lexical"]
    assert augmented[0]["graph_paths"] == [{"kind": "direct", "node_id": "a", "node_name": "概念a"}]
    assert snapshot["difference"] == {"shared": ["lexical"], "added": ["source-a"], "removed": []}
    assert len({e["id"] for e in augmented}) == len(augmented) <= snapshot["evidence_budget"]
    assert basic[0]["text"] == augmented[1]["text"]
    assert basic[0]["material_version"] == augmented[1]["material_version"]
    assert not record["assessment"] and not record["is_stale"]
    # 固定预算为 1 时补入直接依据，必须如实记录被移出的词面命中。
    smaller = compare(client, evidence_budget=1)["snapshot"]
    assert smaller["difference"] == {"shared": [], "added": ["source-a"], "removed": ["lexical"]}
    empty = compare(client, node_ids=[])["snapshot"]
    assert empty["basic"]["evidence"] == empty["graph_augmented"]["evidence"]


def test_only_confirmed_one_hop_with_active_sources(graph_sources):
    client, _ = graph_sources
    snapshot = compare(client, evidence_budget=10)["snapshot"]
    evidence = {e["id"]: e for e in snapshot["graph_augmented"]["evidence"]}
    assert set(evidence) == {"source-a", "source-b", "lexical"}
    path = evidence["source-b"]["graph_paths"][0]
    assert (path["via_node_id"], path["node_id"], path["edge_id"]) == ("a", "b", "edge-ab")
    assert path["edge_chunk_id"] == "source-a"
    reverse = compare(client, node_ids=["b"], evidence_budget=10)["snapshot"]
    source_a = next(e for e in reverse["graph_augmented"]["evidence"] if e["id"] == "source-a")
    reverse_path = source_a["graph_paths"][0]
    assert reverse_path["via_node_id"] == "b"
    assert (reverse_path["edge_source_id"], reverse_path["edge_target_id"]) == ("a", "b")
    assert (
        client.post(COMPARISONS, json={"question_text": "anchor", "node_ids": ["f"]}).status_code
        == 409
    )


def test_saved_snapshot_and_manual_review_survive_material_replacement(graph_sources):
    client, engine = graph_sources
    record = compare(client)
    path = f"{COMPARISONS}/{record['id']}"
    review = {
        "reviewer": "核查教师",
        "relevance": {"source-a": "irrelevant", "lexical": "relevant"},
        "outcome": "worse",
        "note": "补入的直接依据与提问无关。",
    }
    assert client.patch(f"{path}/assessment", json=review).status_code == 200
    with Session(engine) as session:
        old = session.get(Material, "experiment-material")
        old.active = False
        session.add(
            Material(course_id="demo-nlp", title=old.title, document_id=old.document_id, version=2)
        )
        session.get(Course, "demo-nlp").graph_version += 1
        session.commit()
    saved = client.get(path).json()
    assert saved["is_stale"]
    assert saved["snapshot"] == record["snapshot"]
    assert saved["assessment"]["outcome"] == "worse"
    exported = client.get(f"{path}/export")
    assert "attachment" in exported.headers["content-disposition"]
    assert exported.json() == saved
    assert all(
        e["material_id"] != "experiment-material"
        for e in compare(client)["snapshot"]["graph_augmented"]["evidence"]
    )
    review["relevance"] = {"not-in-this-comparison": "relevant"}
    assert client.patch(f"{path}/assessment", json=review).status_code == 422


def test_comparisons_and_question_context_are_course_scoped(graph_sources):
    client, _ = graph_sources
    record = compare(client)
    other = client.post("/api/v1/courses", json={"title": "另一门课"}).json()["id"]
    other_root = f"/api/v1/courses/{other}"
    for suffix in ("", "/export"):
        assert (
            client.get(f"{other_root}/evidence/comparisons/{record['id']}{suffix}").status_code
            == 404
        )
    assert client.get(f"{other_root}/evidence/comparisons").json() == []
    assert client.get(f"{other_root}/nodes/a/questions").status_code == 404
    assert (
        client.post(
            f"{other_root}/evidence/comparisons",
            json={"question_text": "anchor", "node_ids": ["a"]},
        ).status_code
        == 404
    )
    q = client.post(
        f"{ROOT}/questions/match", json={"question_text": "注意力", "method": "name"}
    ).json()
    assert (
        client.post(
            COMPARISONS, json={"question_text": "anchor", "question_id": q["id"]}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{other_root}/evidence/comparisons",
            json={"question_text": q["text"], "question_id": q["id"]},
        ).status_code
        == 404
    )
    bound = compare(client, question_text=q["text"], question_id=q["id"])
    assert bound["snapshot"]["question_context"]["model_version"] == q["model_version"]


def test_node_questions_keeps_original_predictions_and_finds_older_records(api):
    client, engine = api
    q = client.post(
        f"{ROOT}/questions/match", json={"question_text": "注意力机制", "method": "name"}
    ).json()
    predictions = q["predictions"]
    with Session(engine) as session:
        session.add_all(
            Question(
                course_id="demo-nlp",
                text=f"无关问题{i}",
                graph_version=1,
                model_version="test",
                created_at=datetime.now(UTC) + timedelta(seconds=i),
            )
            for i in range(105)
        )
        session.commit()
    assert q["id"] not in {v["id"] for v in client.get(f"{ROOT}/questions").json()}
    related_path = f"{ROOT}/nodes/demo-attention/questions"
    result = client.get(related_path).json()
    assert result["total"] == 1 and result["items"][0]["node_relation"] == "predicted"
    changed = client.post(
        f"{ROOT}/questions/{q['id']}/links", json={"node_ids": ["demo-tokenization"]}
    ).json()
    assert changed["predictions"] == predictions
    assert client.get(related_path).json()["items"][0]["node_relation"] == "not_selected"
    assert (
        client.get(f"{ROOT}/nodes/demo-tokenization/questions").json()["items"][0]["node_relation"]
        == "confirmed"
    )
    client.post(f"{ROOT}/questions/{q['id']}/links", json={"node_ids": []})
    assert client.get(related_path).json()["items"][0]["predictions"] == predictions
    assert client.get(f"{ROOT}/nodes/demo-tokenization/questions").json()["total"] == 0
