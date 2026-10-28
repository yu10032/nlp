import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from ta_backend.config import Settings
from ta_backend.services.generation import ExternalAPIProvider, GenerationError

ROOT = "/api/v1/courses/demo-nlp"


def quiz_payload():
    return {
        "title": "注意力机制练习",
        "target_node_ids": ["demo-attention"],
        "body": {
            "difficulty": "basic",
            "items": [
                {
                    "type": "single_choice",
                    "stem": "注意力机制如何汇总值向量？",
                    "options": ["加权求和", "全部丢弃", "固定取首项", "不处理"],
                    "answer": "A",
                    "explanation": "根据查询与键的匹配程度分配权重。",
                    "node_ids": ["demo-attention"],
                    "citation_ids": ["demo-chunk-2"],
                }
            ],
        },
    }


def lesson_payload(quiz_id=None):
    return {
        "title": "注意力课堂",
        "target_node_ids": ["demo-attention"],
        "body": {
            "duration": 45,
            "objectives": "解释注意力的加权汇总",
            "key_questions": "权重如何分配？",
            "segments": [
                {
                    "title": "原理与讨论",
                    "minutes": 45,
                    "content": "依据原文讨论加权求和。",
                    "activity": "提问",
                    "example": "不同权重的对比",
                    "node_ids": ["demo-attention"],
                    "citation_ids": ["demo-chunk-2"],
                    "quiz_ids": [quiz_id] if quiz_id else [],
                }
            ],
        },
    }


def create(client, kind, payload):
    response = client.post(f"{ROOT}/teaching/{kind}", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def review(client, kind, content, result="approved"):
    return client.post(
        f"{ROOT}/teaching/{kind}/{content['id']}/review",
        json={
            "expected_version": content["version"],
            "reviewer": "测试教师",
            "result": result,
        },
    )


def test_quiz_and_lesson_review_export_and_coverage(api):
    client, _ = api
    quiz = create(client, "quiz", quiz_payload())
    assert client.get(f"{ROOT}/coverage").json()["metrics"]["quiz"]["covered"] == 0
    assert review(client, "quiz", quiz).status_code == 200
    lesson = create(client, "lesson", lesson_payload(quiz["id"]))
    assert review(client, "lesson", lesson).status_code == 200
    export = client.get(f"{ROOT}/teaching/lesson/{lesson['id']}/export")
    assert export.status_code == 200
    assert "45 分钟" in export.text and "注意力机制如何汇总" in export.text
    coverage = client.get(f"{ROOT}/coverage").json()
    assert coverage["metrics"]["quiz"]["covered"] == 1
    assert coverage["metrics"]["lesson"]["covered"] == 1


def test_incomplete_drafts_and_duplicate_items_cannot_be_approved(api):
    client, _ = api
    payload = quiz_payload()
    payload["body"]["items"][0]["answer"] = "E"
    quiz = create(client, "quiz", payload)
    assert review(client, "quiz", quiz).status_code == 422
    payload = quiz_payload()
    payload["body"]["items"].append(deepcopy(payload["body"]["items"][0]))
    quiz = create(client, "quiz", payload)
    assert "相似" in review(client, "quiz", quiz).text
    payload = lesson_payload()
    payload["body"]["segments"][0]["minutes"] = 40
    lesson = create(client, "lesson", payload)
    assert "40" in review(client, "lesson", lesson).text


def test_leaf_links_determine_coverage_and_must_cover_scope_before_review(api):
    client, _ = api
    payload = quiz_payload()
    payload["target_node_ids"].append("demo-transformer")
    quiz = create(client, "quiz", payload)
    assert quiz["node_ids"] == ["demo-attention"]
    assert review(client, "quiz", quiz).status_code == 422
    assert client.get(f"{ROOT}/coverage").json()["metrics"]["quiz"]["covered"] == 0


def test_quiz_edit_invalidates_dependent_lesson_and_version_conflicts(api):
    client, _ = api
    quiz = create(client, "quiz", quiz_payload())
    assert review(client, "quiz", quiz).status_code == 200
    lesson = create(client, "lesson", lesson_payload(quiz["id"]))
    assert review(client, "lesson", lesson).status_code == 200
    path = f"{ROOT}/teaching/quiz/{quiz['id']}"
    changed = client.patch(path, json={**quiz_payload(), "expected_version": 1})
    assert changed.json()["status"] == "stale_review"
    assert len(changed.json()["revisions"]) == 2
    assert client.patch(path, json={**quiz_payload(), "expected_version": 1}).status_code == 409
    stale = client.get(f"{ROOT}/teaching/lesson/{lesson['id']}").json()
    assert stale["status"] == "stale_review"
    assert client.get(f"{ROOT}/coverage").json()["metrics"]["lesson"]["covered"] == 0
    assert review(client, "lesson", stale).status_code == 422


def test_teaching_boundaries_and_disabled_generation(api):
    client, _ = api
    quiz = create(client, "quiz", quiz_payload())
    other = client.post("/api/v1/courses", json={"title": "其他课程"}).json()["id"]
    assert client.get(f"/api/v1/courses/{other}/teaching/quiz/{quiz['id']}").status_code == 404
    assert client.get(f"{ROOT}/teaching/lesson/{quiz['id']}").status_code == 404
    assert (
        client.patch(
            f"{ROOT}/drafts/{quiz['id']}",
            json={
                "title": "绕过结构",
                "answer": "文本",
                "expected_version": 1,
            },
        ).status_code
        == 422
    )
    response = client.post(f"{ROOT}/teaching/quiz", json={**quiz_payload(), "generate": True})
    assert response.status_code == 503
    assert len(client.get(f"{ROOT}/teaching/quiz").json()) == 1


def test_replaced_quiz_evidence_invalidates_lesson_even_with_different_direct_sources(api):
    client, _ = api
    first = client.post(
        f"{ROOT}/documents",
        files={
            "file": ("notes.md", "# 注意力\n\n根据权重汇总值向量。".encode()),
        },
    ).json()
    chunk = client.get(f"{ROOT}/documents/{first['material_id']}/chunks").json()[0]
    payload = quiz_payload()
    payload["body"]["items"][0]["citation_ids"] = [chunk["id"]]
    quiz = create(client, "quiz", payload)
    assert review(client, "quiz", quiz).status_code == 200
    lesson = create(client, "lesson", lesson_payload(quiz["id"]))
    assert review(client, "lesson", lesson).status_code == 200
    client.post(
        f"{ROOT}/documents?replaces_id={first['material_id']}",
        files={
            "file": ("notes.md", "# 注意力\n\n新版课程资料。".encode()),
        },
    )
    saved = client.get(f"{ROOT}/teaching/lesson/{lesson['id']}").json()
    assert saved["status"] == "stale_review"
    assert saved["citations"][0]["active"] is True
    assert client.get(f"{ROOT}/teaching/lesson/{lesson['id']}/export").status_code == 409


def test_teaching_adapter_checks_generated_scope_count_and_duration(monkeypatch):
    from ta_backend.services import generation

    original = httpx.AsyncClient
    returned = quiz_payload()["body"]
    captured = {}

    def handle(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(returned)}}]}
        )

    monkeypatch.setattr(
        generation.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    provider = ExternalAPIProvider(
        Settings(
            database_url="sqlite:///:memory:",
            llm_base_url="https://test.example/v1",
            llm_api_key="test",
            llm_model="test",
        )
    )
    spec = {**quiz_payload()["body"], "nodes": [{"id": "demo-attention", "name": "注意力"}]}
    evidence = [{"id": "demo-chunk-2", "text": "加权求和"}]
    answer, info = asyncio.run(provider.generate_teaching("quiz", spec, evidence))
    assert answer.items[0].answer == "A" and info["prompt_version"] == "quiz-v1"
    assert "schema" in json.loads(captured["messages"][1]["content"])
    returned = deepcopy(returned)
    returned["items"][0]["citation_ids"] = ["foreign"]
    with pytest.raises(GenerationError, match="引用"):
        asyncio.run(provider.generate_teaching("quiz", spec, evidence))
    returned = lesson_payload()["body"]
    spec = {**deepcopy(returned), "nodes": spec["nodes"]}
    valid, _ = asyncio.run(provider.generate_teaching("lesson", spec, evidence))
    assert valid.duration == 45
    returned["segments"][0]["minutes"] = 40
    with pytest.raises(GenerationError, match="分钟"):
        asyncio.run(provider.generate_teaching("lesson", spec, evidence))


def test_generated_content_is_persisted_as_unreviewed_structured_draft(api):
    from ta_backend.services.teaching import QuizBody

    client, _ = api

    class Provider:
        async def generate_teaching(self, kind, spec, evidence):
            assert kind == "quiz" and evidence and spec["nodes"]
            return QuizBody.model_validate(quiz_payload()["body"]), {"provider": "test-only"}

    client.app.state.generation_provider = Provider()
    quiz = create(client, "quiz", {**quiz_payload(), "generate": True})
    assert quiz["status"] == "draft"
    assert quiz["body"]["items"][0]["stem"] == quiz_payload()["body"]["items"][0]["stem"]
    assert quiz["generation_info"]["provider"] == "test-only"


def test_batch_import_retains_original_questions_and_separate_predictions(api):
    client, _ = api
    response = client.post(
        f"{ROOT}/questions/batch",
        json={
            "questions": [
                {"question_text": "注意力机制是什么？"},
                {"question_text": "考试几点开始？"},
            ]
        },
    )
    assert response.status_code == 201
    questions = response.json()
    assert len(questions) == 2 and all(q["needs_review"] for q in questions)
    assert questions[1]["predictions"] == []
    confirmed = client.post(f"{ROOT}/questions/{questions[0]['id']}/links", json={"node_ids": []})
    assert confirmed.json()["predictions"] == questions[0]["predictions"]


@pytest.mark.parametrize(
    ("status", "expected_code"),
    [
        (None, "generation_connection"),
        (401, "generation_auth"),
        (404, "generation_not_found"),
        (429, "generation_limit"),
        (503, "generation_unavailable"),
    ],
)
def test_provider_failures_give_actionable_errors_without_exposing_credentials(
    monkeypatch, status, expected_code
):
    from ta_backend.services import generation

    original = httpx.AsyncClient

    def handle(request):
        if status is None:
            raise httpx.ConnectError("connection failed", request=request)
        return httpx.Response(status, text="upstream internal details")

    monkeypatch.setattr(
        generation.httpx,
        "AsyncClient",
        lambda **kw: original(transport=httpx.MockTransport(handle), **kw),
    )
    provider = ExternalAPIProvider(
        Settings(
            database_url="sqlite:///:memory:",
            llm_base_url="https://test.example/v1",
            llm_api_key="private-test-key",
            llm_model="test",
        )
    )
    with pytest.raises(GenerationError) as caught:
        asyncio.run(provider.generate_structured("问题", [{"id": "test", "text": "原文"}]))
    assert caught.value.code == expected_code
    assert "private-test-key" not in str(caught.value)
    assert "upstream internal details" not in str(caught.value)
