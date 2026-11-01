import json
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.models import KnowledgeNode, Material, Question, RetrievalComparison
from ta_backend.services.retrieval import retrieval_inputs, retrieve_from_inputs

router = APIRouter(prefix="/courses/{course_id}/evidence/comparisons", tags=["experiments"])


def active_materials(session, course_id):
    return [
        {"id": m.id, "document_id": m.document_id, "title": m.title, "version": m.version}
        for m in session.scalars(
            select(Material)
            .where(Material.course_id == course_id, Material.active)
            .order_by(Material.id)
        )
    ]


def comparison_data(record, course, session):
    return {
        "id": record.id,
        "question_text": record.question_text,
        "created_at": record.created_at,
        "snapshot": record.snapshot,
        "assessment": record.assessment,
        "is_stale": record.snapshot["graph_version"] != course.graph_version
        or record.snapshot["materials"] != active_materials(session, course.id),
    }


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question_text: str = Field(min_length=1, max_length=4000)
    question_id: str | None = None
    node_ids: list[str] = Field(default_factory=list, max_length=10)
    evidence_budget: int = Field(default=5, ge=1, le=10)


@router.post("", status_code=201)
def create_comparison(payload: ComparisonRequest, course: CurrentCourse, session: DbSession):
    nodes = [
        scoped_get(session, KnowledgeNode, n, course.id) for n in dict.fromkeys(payload.node_ids)
    ]
    if any(n.status != "confirmed" for n in nodes):
        raise HTTPException(409, "图谱增强只使用已确认的目标知识点")
    question_context = None
    if payload.question_id:
        question = scoped_get(session, Question, payload.question_id, course.id)
        if question.text != payload.question_text:
            raise HTTPException(409, "原始问题与对照文本不同，请取消原问题关联后重试")
        question_context = {
            "id": question.id,
            "model_version": question.model_version,
            "graph_version": question.graph_version,
        }
    node_ids = [n.id for n in nodes]
    materials = active_materials(session, course.id)
    inputs = retrieval_inputs(session, course.id, payload.question_text, node_ids)
    basic = retrieve_from_inputs(inputs, node_ids, "basic", payload.evidence_budget)
    augmented = retrieve_from_inputs(inputs, node_ids, "graph_augmented", payload.evidence_budget)
    basic_ids = [e["id"] for e in basic["evidence"]]
    augmented_ids = [e["id"] for e in augmented["evidence"]]
    record = RetrievalComparison(
        course_id=course.id,
        question_text=payload.question_text,
        snapshot={
            "graph_version": course.graph_version,
            "materials": materials,
            "nodes": [{"id": n.id, "name": n.name} for n in nodes],
            "question_context": question_context,
            "evidence_budget": payload.evidence_budget,
            "basic": basic,
            "graph_augmented": augmented,
            "difference": {
                "shared": [i for i in basic_ids if i in augmented_ids],
                "added": [i for i in augmented_ids if i not in basic_ids],
                "removed": [i for i in basic_ids if i not in augmented_ids],
            },
        },
    )
    session.add(record)
    session.commit()
    return comparison_data(record, course, session)


@router.get("")
def list_comparisons(course: CurrentCourse, session: DbSession):
    return [
        {"id": r.id, "question_text": r.question_text, "created_at": r.created_at}
        for r in session.scalars(
            select(RetrievalComparison)
            .where(RetrievalComparison.course_id == course.id)
            .order_by(RetrievalComparison.created_at.desc())
            .limit(50)
        )
    ]


@router.get("/{record_id}")
def read_comparison(record_id: str, course: CurrentCourse, session: DbSession):
    return comparison_data(
        scoped_get(session, RetrievalComparison, record_id, course.id), course, session
    )


class Assessment(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    reviewer: str = Field(min_length=1, max_length=80)
    relevance: dict[str, Literal["relevant", "irrelevant", "uncertain"]] = Field(max_length=20)
    outcome: Literal["better", "worse", "mixed", "same", "uncertain"] = "uncertain"
    note: str = Field(default="", max_length=4000)


@router.patch("/{record_id}/assessment")
def assess_comparison(
    record_id: str, payload: Assessment, course: CurrentCourse, session: DbSession
):
    record = scoped_get(session, RetrievalComparison, record_id, course.id)
    allowed = {
        e["id"] for mode in ("basic", "graph_augmented") for e in record.snapshot[mode]["evidence"]
    }
    if not set(payload.relevance) <= allowed:
        raise HTTPException(422, "只能评价本次对照中的证据")
    record.assessment = {**payload.model_dump(), "updated_at": datetime.now(UTC).isoformat()}
    session.commit()
    return comparison_data(record, course, session)


@router.get("/{record_id}/export")
def export_comparison(record_id: str, course: CurrentCourse, session: DbSession):
    data = read_comparison(record_id, course, session)
    data["created_at"] = data["created_at"].isoformat()
    return Response(
        json.dumps(data, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="retrieval-{record_id}.json"'},
    )
