from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.api.drafts import (
    DraftReview,
    DraftWrite,
    draft_data,
    export_draft,
    require_reviewable,
    review_draft,
    save_revision,
)
from ta_backend.api.graph import checked_chunks
from ta_backend.models import KnowledgeNode, TeachingContent
from ta_backend.services.generation import GenerationError
from ta_backend.services.retrieval import retrieve
from ta_backend.services.teaching import (
    LessonBody,
    QuizBody,
    TeachingKind,
    completeness_issues,
    invalidate_lesson_examples,
    linked_ids,
    render_markdown,
)

router = APIRouter(prefix="/courses/{course_id}/teaching", tags=["teaching"])


class TeachingWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    target_node_ids: list[str] = Field(min_length=1, max_length=5)
    body: QuizBody | LessonBody


class TeachingCreate(TeachingWrite):
    generate: bool = False


class TeachingUpdate(TeachingWrite):
    expected_version: int = Field(ge=1)


def get_content(session, kind, content_id, course_id):
    content = scoped_get(session, TeachingContent, content_id, course_id)
    if content.kind != kind:
        raise HTTPException(404, "当前类型中没有这份内容")
    return content


def check_scope(session, kind, body, target_ids, course_id):
    nodes = [scoped_get(session, KnowledgeNode, node_id, course_id) for node_id in target_ids]
    if any(node.kind == "chapter" or node.status != "confirmed" for node in nodes):
        raise HTTPException(422, "请选择已确认的具体知识点；章节可展开选择下级知识点")
    if not set(linked_ids(kind, body, "node_ids")).issubset(target_ids):
        raise HTTPException(422, "题目或环节关联了本次目标以外的知识点")
    checked_chunks(session, linked_ids(kind, body, "citation_ids"), course_id)
    return nodes


def lesson_examples(session, body, course_id, check_versions=False):
    examples = {}
    for quiz_id in linked_ids("lesson", body, "quiz_ids"):
        quiz = get_content(session, "quiz", quiz_id, course_id)
        require_reviewable(quiz, session, course_id)
        if quiz.status != "approved" or quiz.reviewed_version != quiz.version or quiz.archived:
            raise HTTPException(422, "关联例题已失效或尚未审核，请重新选择")
        if (
            check_versions
            and body.get("examples", {}).get(quiz_id, {}).get("version") != quiz.version
        ):
            raise HTTPException(422, "关联例题已更新，请重新保存备课并核查")
        examples[quiz_id] = {
            "title": quiz.title,
            "version": quiz.version,
            "answer": quiz.body["answer"],
        }
    return examples


def check_teaching_review(content, session, course_id):
    issues = completeness_issues(content.kind, content.body)
    if issues:
        raise HTTPException(422, "；".join(issues))
    target_ids = content.body["target_node_ids"]
    check_scope(session, content.kind, content.body, target_ids, course_id)
    if set(linked_ids(content.kind, content.body, "node_ids")) != set(target_ids):
        raise HTTPException(422, "仍有目标知识点未关联到具体题目或课堂环节")
    if content.kind == "lesson":
        lesson_examples(session, content.body, course_id, check_versions=True)


def write_content(content, payload, kind, course_id, session):
    schema = QuizBody if kind == "quiz" else LessonBody
    if not isinstance(payload.body, schema):
        raise HTTPException(422, "内容结构与出题或备课类型不符")
    body = payload.body.model_dump()
    nodes = check_scope(session, kind, body, payload.target_node_ids, course_id)
    body["target_node_ids"] = list(dict.fromkeys(payload.target_node_ids))
    if kind == "lesson":
        body["examples"] = lesson_examples(session, body, course_id)
    answer = render_markdown(kind, body, {node.id: node.name for node in nodes})
    return save_revision(
        content,
        DraftWrite.model_construct(
            title=payload.title,
            answer=answer,
            node_ids=linked_ids(kind, body, "node_ids"),
            citation_ids=linked_ids(kind, body, "citation_ids"),
        ),
        session,
        course_id,
        body=body,
    )


@router.get("/{kind}")
def list_contents(kind: TeachingKind, course: CurrentCourse, session: DbSession):
    return [
        {
            "id": item.id,
            "title": item.title,
            "status": item.status,
            "version": item.version,
            "updated_at": item.updated_at,
        }
        for item in session.scalars(
            select(TeachingContent)
            .where(
                TeachingContent.course_id == course.id,
                TeachingContent.kind == kind,
                TeachingContent.archived.is_(False),
            )
            .order_by(TeachingContent.updated_at.desc())
            .limit(100)
        )
    ]


@router.post("/{kind}", status_code=201)
async def create_content(
    kind: TeachingKind,
    payload: TeachingCreate,
    course: CurrentCourse,
    session: DbSession,
    request: Request,
):
    schema = QuizBody if kind == "quiz" else LessonBody
    if not isinstance(payload.body, schema):
        raise HTTPException(422, "内容结构与出题或备课类型不符")
    content = TeachingContent(course_id=course.id, kind=kind, version=1, body={})
    if payload.generate:
        nodes = check_scope(
            session, kind, payload.body.model_dump(), payload.target_node_ids, course.id
        )
        spec = payload.body.model_dump()
        if kind == "lesson":
            spec["examples"] = lesson_examples(session, spec, course.id)
        query = " ".join(node.name for node in nodes)
        result = retrieve(
            session, course.id, query, payload.target_node_ids, "graph_augmented", budget=10
        )
        if result["missing_evidence"]:
            raise HTTPException(422, "目标知识点没有可用课程依据，请先补充资料")
        spec["nodes"] = [{"id": node.id, "name": node.name} for node in nodes]
        try:
            generated, info = await request.app.state.generation_provider.generate_teaching(
                kind, spec, result["evidence"]
            )
        except GenerationError as error:
            raise HTTPException(503, {"code": error.code, "message": str(error)}) from error
        payload.body = generated
        content.generation_info = info
    return write_content(content, payload, kind, course.id, session)


@router.get("/{kind}/{content_id}")
def read_content(kind: TeachingKind, content_id: str, course: CurrentCourse, session: DbSession):
    return draft_data(get_content(session, kind, content_id, course.id), session)


@router.patch("/{kind}/{content_id}")
def update_content(
    kind: TeachingKind,
    content_id: str,
    payload: TeachingUpdate,
    course: CurrentCourse,
    session: DbSession,
):
    content = get_content(session, kind, content_id, course.id)
    if payload.expected_version != content.version:
        raise HTTPException(409, "内容已被更新，请重新打开后编辑")
    if kind == "quiz":
        invalidate_lesson_examples(session, content.id, content.course_id)
    content.version += 1
    content.status = (
        "stale_review"
        if content.reviewed_version is not None or content.status == "stale_review"
        else "draft"
    )
    content.reviewed_version = None
    return write_content(content, payload, kind, course.id, session)


@router.post("/{kind}/{content_id}/review")
def review_content(
    kind: TeachingKind,
    content_id: str,
    payload: DraftReview,
    course: CurrentCourse,
    session: DbSession,
):
    get_content(session, kind, content_id, course.id)
    return review_draft(content_id, payload, course, session)


@router.get("/{kind}/{content_id}/export")
def export_content(kind: TeachingKind, content_id: str, course: CurrentCourse, session: DbSession):
    get_content(session, kind, content_id, course.id)
    return export_draft(content_id, course, session)
