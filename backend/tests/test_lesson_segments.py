import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from sqlalchemy.orm import Session
from ta_backend.config import Settings
from ta_backend.models import Chunk, TeachingContent
from ta_backend.services.generation import ExternalAPIProvider, GeneratedSegment, GenerationError
from ta_backend.services.retrieval import retrieve
from test_teaching import ROOT, create, full_lesson_payload


def confirmed_plan(client):
    payload = full_lesson_payload()
    for part in payload["body"]["segments"]:
        for key in (
            "content",
            "activity",
            "example",
            "student_activity",
            "expected_response",
            "check_for_understanding",
            "misconceptions",
        ):
            part[key] = ""
    saved = create(client, "lesson", payload)
    response = client.post(
        f"{ROOT}/teaching/lesson/{saved['id']}/confirm-plan",
        json={"expected_version": saved["version"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def generate(client, lesson, index=0, **extra):
    return client.post(
        f"{ROOT}/teaching/lesson/{lesson['id']}/segments/{lesson['body']['segments'][index]['id']}/generate",
        json={"expected_version": lesson["version"], **extra},
    )


class SegmentProvider:
    def __init__(self):
        self.fail_index = None
        self.calls = []

    async def generate_lesson_segment(self, spec, evidence):
        self.calls.append(spec)
        index = spec["segment_index"]
        if index == self.fail_index:
            raise GenerationError("generation_timeout", "模拟超时")
        part = {
            **full_lesson_payload()["body"]["segments"][index],
            **{
                key: spec["segment"][key]
                for key in ("id", "title", "stage", "minutes", "node_ids", "quiz_ids")
            },
        }
        part["content"] += spec["rewrite_instruction"]
        return GeneratedSegment(
            segment=part, preparation="先备知识与工具", homework="巩固题和参考要点"
        ), {"provider": "offline-test"}


def test_partial_failure_keeps_completed_segments_and_resume_uses_new_version(api):
    client, _ = api
    provider = SegmentProvider()
    client.app.state.generation_provider = provider
    plan = confirmed_plan(client)
    first = generate(client, plan).json()
    assert first["body"]["segments"][0]["content"]
    assert first["version"] == plan["version"] + 1
    provider.fail_index = 1
    response = generate(client, first, 1)
    assert response.status_code == 503
    current = client.get(f"{ROOT}/teaching/lesson/{plan['id']}").json()
    assert current["version"] == first["version"]
    assert current["body"] == first["body"]
    provider.fail_index = None
    second = generate(client, current, 1).json()
    assert second["body"]["segments"][0] == first["body"]["segments"][0]
    assert second["body"]["segments"][1]["content"]
    assert not second["body"]["segments"][2]["content"]
    assert generate(client, first, 2).status_code == 409


def test_rewrite_only_updates_selected_segment_and_preserves_teacher_text(api):
    client, _ = api
    client.app.state.generation_provider = SegmentProvider()
    plan = confirmed_plan(client)
    first = generate(client, plan).json()
    payload = {
        "title": first["title"],
        "target_node_ids": first["body"]["target_node_ids"],
        "body": deepcopy(first["body"]),
        "expected_version": first["version"],
    }
    payload["body"]["segments"][2]["content"] = "教师手工内容，应保留。"
    payload["body"]["preparation"] = "教师自定课前准备"
    saved = client.patch(f"{ROOT}/teaching/lesson/{first['id']}", json=payload).json()
    assert saved["body"]["plan_confirmed"]
    rewritten = generate(client, saved, rewrite_instruction="补充直观比喻").json()
    assert rewritten["body"]["segments"][0]["content"].endswith("补充直观比喻")
    assert rewritten["body"]["segments"][1:] == saved["body"]["segments"][1:]
    assert rewritten["body"]["preparation"] == "教师自定课前准备"
    payload.update(body=deepcopy(rewritten["body"]), expected_version=rewritten["version"])
    payload["body"]["segments"][1]["title"] = "修改后的安排"
    changed = client.patch(f"{ROOT}/teaching/lesson/{first['id']}", json=payload).json()
    assert not changed["body"]["plan_confirmed"]
    assert generate(client, changed).status_code == 422


def test_generation_does_not_overwrite_edits_made_during_request(api):
    client, engine = api
    plan = confirmed_plan(client)

    class ConcurrentProvider(SegmentProvider):
        async def generate_lesson_segment(self, spec, evidence):
            with Session(engine) as session:
                content = session.get(TeachingContent, plan["id"])
                content.title = "教师并行修改后的标题"
                content.version += 1
                session.commit()
            return await super().generate_lesson_segment(spec, evidence)

    client.app.state.generation_provider = ConcurrentProvider()
    assert generate(client, plan).status_code == 409
    current = client.get(f"{ROOT}/teaching/lesson/{plan['id']}").json()
    assert current["title"] == "教师并行修改后的标题"
    assert not current["body"]["segments"][0]["content"]


def test_plan_cannot_be_confirmed_with_wrong_time_or_forged_confirmation(api):
    client, _ = api
    payload = full_lesson_payload()
    payload["body"]["plan_confirmed"] = True
    payload["body"]["duration"] = 90
    lesson = create(client, "lesson", payload)
    assert not lesson["body"]["plan_confirmed"]
    assert generate(client, lesson).status_code == 422
    response = client.post(
        f"{ROOT}/teaching/lesson/{lesson['id']}/confirm-plan", json={"expected_version": 1}
    )
    assert response.status_code == 422
    assert "时长" in response.text


def test_targeted_retrieval_allocates_direct_sources_before_other_hits(api):
    _, engine = api
    with Session(engine) as session:
        session.add_all(
            Chunk(
                course_id="demo-nlp",
                material_id="demo-material",
                text="注意力机制 注意力机制",
                locator=f"补充 {index}",
            )
            for index in range(3)
        )
        session.flush()
        result = retrieve(
            session,
            "demo-nlp",
            "注意力机制 注意力机制",
            ["demo-attention", "demo-tokenization"],
            "graph_augmented",
            budget=2,
        )
    assert len(result["evidence"]) == 2
    assert all(
        item["has_active_source"] and item["citation_ids"] for item in result["node_evidence"]
    )


def test_segment_route_is_scoped_to_course(api):
    client, _ = api
    lesson = confirmed_plan(client)
    other = client.post("/api/v1/courses", json={"title": "其他课程"}).json()["id"]
    response = client.post(
        f"/api/v1/courses/{other}/teaching/lesson/{lesson['id']}/confirm-plan",
        json={"expected_version": lesson["version"]},
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "change", [None, "foreign_citation", "short", "changed_plan", "missing_activity"]
)
def test_segment_adapter_validates_the_requested_plan_and_full_content(monkeypatch, change):
    from ta_backend.services import generation

    part = full_lesson_payload()["body"]["segments"][1]
    part["id"] = "test-segment"
    returned = deepcopy(part)
    returned["content"] *= 2
    if change == "foreign_citation":
        returned["citation_ids"] = ["other-course"]
    elif change == "short":
        returned["content"] = "介绍注意力原理。"
    elif change == "changed_plan":
        returned["minutes"] += 1
    elif change == "missing_activity":
        returned["expected_response"] = ""
    original = httpx.AsyncClient
    captured = {}

    def handle(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps({"segment": returned})}}]}
        )

    monkeypatch.setattr(
        generation.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    provider = ExternalAPIProvider(
        Settings(
            database_url="sqlite:///:memory:",
            llm_base_url="https://test.example",
            llm_api_key="test",
            llm_model="test",
        )
    )
    spec = {"segment": part, "segment_index": 1}
    evidence = [{"id": "demo-chunk-2", "text": "加权汇总"}]
    if change:
        with pytest.raises(GenerationError) as error:
            asyncio.run(provider.generate_lesson_segment(spec, evidence))
        assert error.value.code == "invalid_generation"
    else:
        result, info = asyncio.run(provider.generate_lesson_segment(spec, evidence))
        assert result.segment.id == part["id"]
        assert info["prompt_version"] == "lesson-segment-v1"
        assert captured["max_tokens"] == part["minutes"] * 320
