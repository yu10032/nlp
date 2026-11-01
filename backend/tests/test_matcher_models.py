from types import SimpleNamespace

import pytest
from course_matcher.data import split_families
from course_matcher.evaluation import lexical_scores, metrics, predict, select_threshold
from sqlalchemy import select
from sqlalchemy.orm import Session
from ta_backend.models import Course, KnowledgeNode
from ta_backend.services.retrieval import tfidf_scores

ROOT = "/api/v1/courses/demo-nlp"


def fake_model(engine):
    with Session(engine) as session:
        course = session.get(Course, "demo-nlp")
        nodes = session.scalars(
            select(KnowledgeNode)
            .where(
                KnowledgeNode.course_id == course.id,
                KnowledgeNode.status == "confirmed",
                KnowledgeNode.kind != "chapter",
            )
            .order_by(KnowledgeNode.id)
        ).all()
        snapshot = [
            {"id": n.id, "name": n.name, "aliases": n.aliases, "description": n.description}
            for n in nodes
        ]
        info = {
            "run_id": "test-run",
            "course_id": course.id,
            "graph_version": course.graph_version,
            "nodes": snapshot,
            "data_status": "development",
            "preferred_method": "tfidf",
            "thresholds": {"embedding": 0.6, "mlp": 0.7, "tfidf": 0.1},
        }
    values = [0.9 if n["id"] == "demo-attention" else 0.1 for n in snapshot]
    return SimpleNamespace(manifest=info, score=lambda _: {"embedding": values, "mlp": values})


def test_compare_is_read_only_and_explicit_mlp_keeps_real_method_version(api):
    client, engine = api
    client.app.state.local_matcher = fake_model(engine)
    before = client.get(ROOT + "/questions").json()
    response = client.post(ROOT + "/matches/compare", json={"question": "注意力怎么计算？"})
    assert response.status_code == 200
    assert {r["method"] for r in response.json()["results"]} == {
        "name",
        "tfidf",
        "embedding",
        "mlp",
    }
    assert client.get(ROOT + "/questions").json() == before
    matched = client.post(
        ROOT + "/questions/match", json={"question_text": "注意力怎么计算？", "method": "mlp"}
    ).json()
    assert matched["model_version"] == "test-run/mlp"
    assert matched["predictions"][0]["node_id"] == "demo-attention"
    confirmed = client.post(
        ROOT + f"/questions/{matched['id']}/links", json={"node_ids": []}
    ).json()
    assert confirmed["predictions"] == matched["predictions"]
    assert client.get(ROOT + "/matcher").json()["active_method"] == "tfidf"


def test_course_and_graph_changes_disable_model_without_mislabeling_baselines(api):
    client, engine = api
    client.app.state.local_matcher = fake_model(engine)
    other = client.post("/api/v1/courses", json={"title": "另一门课"}).json()["id"]
    assert (
        client.post(
            f"/api/v1/courses/{other}/matches", json={"question": "问题", "method": "mlp"}
        ).status_code
        == 409
    )
    with Session(engine) as session:
        session.get(Course, "demo-nlp").graph_version += 1
        session.commit()
    status = client.get(ROOT + "/matcher").json()
    assert "版本" in status["scope_reason"]
    assert status["active_method"] == "tfidf"
    result = client.post(ROOT + "/questions/match", json={"question_text": "注意力"}).json()
    assert result["model_version"] == "tfidf-bigram-v1"
    assert (
        client.post(ROOT + "/matches", json={"question": "注意力", "method": "mlp"}).status_code
        == 409
    )


def test_disabled_model_is_visible_and_legacy_name_endpoint_stays_compatible(api):
    client, _ = api
    assert client.get(ROOT + "/matcher").json()["scope_reason"]
    assert (
        client.post(ROOT + "/matches", json={"question": "attention"}).json()["method"]
        == "name-baseline-v1"
    )
    assert (
        client.post(
            ROOT + "/questions/match", json={"question_text": "注意力", "method": "mlp"}
        ).status_code
        == 409
    )
    assert client.get(ROOT + "/experiments").json()["run"] is None


def test_training_split_metrics_and_lexical_parity():
    rows = [{"family_id": f"f{i}", "question": str(j)} for i in range(20) for j in range(3)]
    split = split_families(rows)
    families = [{row["family_id"] for row in values} for values in split.values()]
    assert sum(map(len, split.values())) == len(rows)
    assert (
        not families[0] & families[1]
        and not families[1] & families[2]
        and not families[0] & families[2]
    )
    score = metrics([["a", "b"], [], ["c"]], [["a"], ["b"], ["c"]])
    assert score["micro_f1"] == pytest.approx(2 / 3)
    assert score["no_match_false_link_rate"] == 1
    assert metrics([[]], [[]])["exact_match"] == 1
    texts = ["数据平滑 缓解零概率", "Ngram MODEL", ""]
    assert lexical_scores("没见过的词概率", texts) == pytest.approx(
        tfidf_scores("没见过的词概率", texts)
    )
    assert predict([0.9, -1.0], ["a", "b"], 0.7) == ["a"]
    assert select_threshold([[0.9], [0.2]], [{"node_ids": ["a"]}, {"node_ids": []}], ["a"]) == 0.9
