from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.api.graph import checked_chunks
from ta_backend.models import (
    Chunk,
    ContentCitation,
    ContentNode,
    ContentRevision,
    KnowledgeNode,
    Material,
    Question,
    ReviewRecord,
    TeachingContent,
    utc_now,
)
from ta_backend.services.generation import GenerationError
from ta_backend.services.retrieval import retrieve

router = APIRouter(prefix="/courses/{course_id}", tags=["drafts"])


class DraftWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    answer: str = Field(default="", max_length=30000)
    node_ids: list[str] = Field(default_factory=list, max_length=10)
    citation_ids: list[str] = Field(default_factory=list, max_length=20)


class DraftCreate(DraftWrite):
    question_id: str
    generate: bool = False
    retrieval_mode: Literal["basic", "graph_augmented"] = "basic"


class DraftUpdate(DraftWrite):
    expected_version: int = Field(ge=1)


class DraftReview(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    expected_version: int = Field(ge=1)
    result: Literal["approved", "rejected"]
    reviewer: str = Field(min_length=1, max_length=80)
    note: str = Field(default="", max_length=1000)


def draft_data(content: TeachingContent, session) -> dict:
    nodes = list(
        session.scalars(
            select(ContentNode.node_id).where(
                ContentNode.content_id == content.id,
            )
        )
    )
    rows = session.execute(
        select(Chunk, Material)
        .join(Material)
        .join(
            ContentCitation,
            ContentCitation.chunk_id == Chunk.id,
        )
        .where(ContentCitation.content_id == content.id)
    )
    citations = [
        {
            "id": chunk.id,
            "material_id": material.id,
            "material_title": material.title,
            "material_version": material.version,
            "text": chunk.text,
            "locator": chunk.locator,
            "section_path": chunk.section_path,
            "active": material.active,
        }
        for chunk, material in rows
    ]
    reviews = session.scalars(
        select(ReviewRecord)
        .where(
            ReviewRecord.content_id == content.id,
        )
        .order_by(ReviewRecord.created_at.desc())
    ).all()
    revisions = session.scalars(
        select(ContentRevision)
        .where(
            ContentRevision.content_id == content.id,
        )
        .order_by(ContentRevision.version.desc())
    ).all()
    return {
        "id": content.id,
        "title": content.title,
        "answer": content.body.get("answer", ""),
        "question_text": session.get(Question, content.question_id).text
        if content.question_id
        else content.title,
        "status": content.status,
        "version": content.version,
        "question_id": content.question_id,
        "node_ids": nodes,
        "citation_ids": [item["id"] for item in citations],
        "citations": citations,
        "generation_info": content.generation_info,
        "updated_at": content.updated_at,
        "reviews": [
            {
                "revision": review.revision,
                "result": review.result,
                "reviewer": review.reviewer,
                "note": review.note,
                "created_at": review.created_at,
            }
            for review in reviews
        ],
        "revisions": [
            {
                "version": revision.version,
                "snapshot": revision.snapshot,
                "created_at": revision.created_at,
            }
            for revision in revisions
        ],
    }


def save_revision(content: TeachingContent, payload: DraftWrite, session, course_id: str):
    checked_chunks(session, payload.citation_ids, course_id)
    for node_id in payload.node_ids:
        scoped_get(session, KnowledgeNode, node_id, course_id)
    content.title = payload.title
    content.body = {**content.body, "answer": payload.answer}
    content.updated_at = utc_now()
    session.add(content)
    session.flush()
    for model in (ContentNode, ContentCitation):
        session.execute(delete(model).where(model.content_id == content.id))
    session.add_all(
        ContentNode(course_id=course_id, content_id=content.id, node_id=node_id)
        for node_id in dict.fromkeys(payload.node_ids)
    )
    session.add_all(
        ContentCitation(course_id=course_id, content_id=content.id, chunk_id=chunk_id)
        for chunk_id in dict.fromkeys(payload.citation_ids)
    )
    session.add(
        ContentRevision(
            course_id=course_id,
            content_id=content.id,
            version=content.version,
            snapshot={
                "title": payload.title,
                "answer": payload.answer,
                "node_ids": list(dict.fromkeys(payload.node_ids)),
                "citation_ids": list(dict.fromkeys(payload.citation_ids)),
                "generation_info": content.generation_info,
            },
        )
    )
    session.commit()
    return draft_data(content, session)


@router.get("/drafts")
def list_drafts(course: CurrentCourse, session: DbSession):
    contents = session.scalars(
        select(TeachingContent)
        .where(
            TeachingContent.course_id == course.id,
            TeachingContent.kind == "qa",
            TeachingContent.archived.is_(False),
        )
        .order_by(TeachingContent.updated_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": content.id,
            "title": content.title,
            "status": content.status,
            "version": content.version,
            "updated_at": content.updated_at,
        }
        for content in contents
    ]


@router.get("/drafts/{draft_id}")
def read_draft(draft_id: str, course: CurrentCourse, session: DbSession):
    return draft_data(scoped_get(session, TeachingContent, draft_id, course.id), session)


@router.post("/drafts", status_code=201)
async def create_draft(
    payload: DraftCreate, course: CurrentCourse, session: DbSession, request: Request
):
    question = scoped_get(session, Question, payload.question_id, course.id)
    for node_id in payload.node_ids:
        scoped_get(session, KnowledgeNode, node_id, course.id)
    content = TeachingContent(
        course_id=course.id, kind="qa", question_id=question.id, version=1, body={}
    )
    if payload.generate:
        result = retrieve(
            session, course.id, question.text, payload.node_ids, payload.retrieval_mode
        )
        if result["missing_evidence"]:
            raise HTTPException(
                422,
                {
                    "code": "insufficient_evidence",
                    "message": "没有找到课程依据，请补充资料或改写问题",
                },
            )
        try:
            generated, info = await request.app.state.generation_provider.generate_structured(
                question.text,
                result["evidence"],
            )
        except GenerationError as error:
            raise HTTPException(503, {"code": error.code, "message": str(error)}) from error
        payload.answer = generated.answer
        payload.citation_ids = generated.citation_ids
        content.body = {"missing_info": generated.missing_info}
        content.generation_info = info
    return save_revision(content, payload, session, course.id)


@router.patch("/drafts/{draft_id}")
def update_draft(draft_id: str, payload: DraftUpdate, course: CurrentCourse, session: DbSession):
    content = scoped_get(session, TeachingContent, draft_id, course.id)
    if content.version != payload.expected_version:
        raise HTTPException(409, "内容已被更新，请重新打开后编辑")
    content.version += 1
    content.status = (
        "stale_review"
        if content.reviewed_version is not None or content.status == "stale_review"
        else "draft"
    )
    content.reviewed_version = None
    return save_revision(content, payload, session, course.id)


def require_reviewable(content, session, course_id):
    if not content.body.get("answer", "").strip():
        raise HTTPException(422, "请先填写答疑正文")
    citation_ids = list(
        session.scalars(
            select(ContentCitation.chunk_id).where(
                ContentCitation.content_id == content.id,
            )
        )
    )
    if not citation_ids:
        raise HTTPException(422, "请关联至少一段课程依据后再审核")
    checked_chunks(session, citation_ids, course_id)
    node_ids = session.scalars(
        select(ContentNode.node_id).where(ContentNode.content_id == content.id)
    )
    for node_id in node_ids:
        if scoped_get(session, KnowledgeNode, node_id, course_id).status != "confirmed":
            raise HTTPException(422, "内容关联了待确认知识点，请先核查图谱")


@router.post("/drafts/{draft_id}/review")
def review_draft(draft_id: str, payload: DraftReview, course: CurrentCourse, session: DbSession):
    content = scoped_get(session, TeachingContent, draft_id, course.id)
    if content.version != payload.expected_version:
        raise HTTPException(409, "正文版本已变化，请重新检查后审核")
    if payload.result == "approved":
        require_reviewable(content, session, course.id)
    content.status = payload.result
    content.reviewed_version = content.version if payload.result == "approved" else None
    session.add(
        ReviewRecord(
            course_id=course.id,
            content_id=content.id,
            revision=content.version,
            result=payload.result,
            reviewer=payload.reviewer,
            note=payload.note,
        )
    )
    session.commit()
    return draft_data(content, session)


@router.get("/drafts/{draft_id}/export")
def export_draft(draft_id: str, course: CurrentCourse, session: DbSession):
    content = scoped_get(session, TeachingContent, draft_id, course.id)
    if content.status != "approved" or content.reviewed_version != content.version:
        raise HTTPException(409, "仅可导出当前版本已审核的内容")
    require_reviewable(content, session, course.id)
    data = draft_data(content, session)
    lines = [f"# {content.title}", "", content.body["answer"], "", "## 课程依据", ""]
    lines.extend(
        f"- {item['material_title']} · v{item['material_version']} · {item['locator']}\n"
        f"  {item['text']}"
        for item in data["citations"]
    )
    return Response(
        "\n".join(lines) + "\n",
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="answer-{content.id}.md"'},
    )
