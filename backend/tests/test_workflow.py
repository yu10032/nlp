from sqlalchemy.orm import Session
from ta_backend.models import ContentCitation, ContentNode, Material, TeachingContent


def test_courses_persist_and_do_not_share_nodes(api):
    client, _ = api
    response = client.post("/api/v1/courses", json={"title": "第二课程"})
    assert response.status_code == 201
    course_id = response.json()["id"]
    assert any(c["id"] == course_id for c in client.get("/api/v1/courses").json())
    assert client.get(f"/api/v1/courses/{course_id}/graph").json() == {
        "version": 1,
        "nodes": [],
        "edges": [],
    }
    assert client.get(f"/api/v1/courses/{course_id}/nodes/demo-attention").status_code == 404
    coverage = client.get(f"/api/v1/courses/{course_id}/coverage").json()
    assert coverage["metrics"]["quiz"] == {"covered": 0, "total": 0, "ratio": None}


def test_graph_has_traceable_evidence(api):
    client, _ = api
    assert len(client.get("/api/v1/courses/demo-nlp/graph").json()["nodes"]) == 5
    detail = client.get("/api/v1/courses/demo-nlp/nodes/demo-attention").json()
    assert detail["evidence"][0]["id"] == "demo-chunk-2"
    assert "加权求和" in detail["evidence"][0]["text"]


def test_baseline_is_explicit_and_does_not_force_a_match(api):
    client, _ = api
    match = client.post("/api/v1/courses/demo-nlp/matches", json={"question": "attention是什么？"})
    assert match.json()["method"] == "name-baseline-v1"
    assert match.json()["matches"][0]["node_id"] == "demo-attention"
    assert (
        client.post("/api/v1/courses/demo-nlp/matches", json={"question": "什么时候考试？"}).json()[
            "matches"
        ]
        == []
    )
    assert (
        client.post("/api/v1/courses/demo-nlp/matches", json={"question": "  "}).status_code == 422
    )


def test_coverage_excludes_drafts_stale_reviews_and_inactive_sources(api):
    client, engine = api
    with Session(engine) as session:
        session.add_all(
            [
                TeachingContent(
                    id="quiz-1",
                    course_id="demo-nlp",
                    kind="quiz",
                    title="已审核题",
                    status="approved",
                    version=1,
                    reviewed_version=1,
                ),
                TeachingContent(id="quiz-2", course_id="demo-nlp", kind="quiz", title="草稿"),
                TeachingContent(
                    id="lesson-1",
                    course_id="demo-nlp",
                    kind="lesson",
                    title="已修改",
                    status="approved",
                    version=2,
                    reviewed_version=1,
                ),
            ]
        )
        session.flush()
        session.add_all(
            [
                ContentNode(course_id="demo-nlp", content_id="quiz-1", node_id="demo-attention"),
                ContentNode(course_id="demo-nlp", content_id="quiz-2", node_id="demo-embedding"),
                ContentNode(
                    course_id="demo-nlp", content_id="lesson-1", node_id="demo-transformer"
                ),
                ContentCitation(course_id="demo-nlp", content_id="quiz-1", chunk_id="demo-chunk-2"),
            ]
        )
        session.commit()
    result = client.get("/api/v1/courses/demo-nlp/coverage").json()
    assert result["metrics"]["material"] == {"covered": 5, "total": 5, "ratio": 1.0}
    assert result["metrics"]["quiz"] == {"covered": 1, "total": 5, "ratio": 0.2}
    assert result["metrics"]["lesson"]["covered"] == 0
    with Session(engine) as session:
        session.get(Material, "demo-material").active = False
        session.commit()
    result = client.get("/api/v1/courses/demo-nlp/coverage").json()
    assert result["metrics"]["material"]["covered"] == 0
    assert result["metrics"]["quiz"]["covered"] == 0


def test_missing_course_returns_404(api):
    client, _ = api
    assert client.get("/api/v1/courses/missing/graph").status_code == 404
