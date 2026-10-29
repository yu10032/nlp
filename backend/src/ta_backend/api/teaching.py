from copy import deepcopy
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
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
from ta_backend.models import KnowledgeNode, Material, TeachingContent
from ta_backend.services.generation import GenerationError
from ta_backend.services.lesson_export import LessonExportError, export_lesson_word
from ta_backend.services.retrieval import retrieve
from ta_backend.services.teaching import (
    LessonBody,
    QuizBody,
    TeachingKind,
    completeness_issues,
    invalidate_lesson_examples,
    lesson_plan,
    lesson_plan_issues,
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


class LessonAction(BaseModel):
    expected_version: int = Field(ge=1)


class SegmentGenerate(LessonAction):
    rewrite_instruction: str = Field(default="", max_length=2000)


def advance_revision(content):
    content.version += 1
    content.status = (
        "stale_review"
        if content.reviewed_version is not None or content.status == "stale_review"
        else "draft"
    )
    content.reviewed_version = None


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
            "student_content": "\n\n".join(
                f"{index}. {item['stem']}\n"
                + "\n".join(
                    f"{letter}. {option}" for letter, option in zip("ABCD", item["options"])
                )
                for index, item in enumerate(quiz.body["items"], 1)
            ),
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


def write_content(content, payload, kind, course_id, session, *, confirm_plan=False):
    schema = QuizBody if kind == "quiz" else LessonBody
    if not isinstance(payload.body, schema):
        raise HTTPException(422, "内容结构与出题或备课类型不符")
    body = payload.body.model_dump()
    nodes = check_scope(session, kind, body, payload.target_node_ids, course_id)
    body["target_node_ids"] = list(dict.fromkeys(payload.target_node_ids))
    if kind == "lesson":
        body["plan_confirmed"] = confirm_plan or (
            content.body.get("plan_confirmed", False)
            and lesson_plan(body) == lesson_plan(content.body)
            and body["target_node_ids"] == content.body["target_node_ids"]
        )
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
            spec["format_version"] = 2
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
    advance_revision(content)
    return write_content(content, payload, kind, course.id, session)


@router.post("/lesson/{content_id}/confirm-plan")
def confirm_lesson_plan(
    content_id: str, payload: LessonAction, course: CurrentCourse, session: DbSession
):
    content = get_content(session, "lesson", content_id, course.id)
    if content.version != payload.expected_version:
        raise HTTPException(409, "内容已被更新，请重新打开后确认")
    body = LessonBody.model_validate(content.body)
    issues = lesson_plan_issues(body.model_dump(), content.body["target_node_ids"])
    if issues:
        raise HTTPException(422, "；".join(issues))
    advance_revision(content)
    return write_content(
        content,
        TeachingWrite(
            title=content.title, target_node_ids=content.body["target_node_ids"], body=body
        ),
        "lesson",
        course.id,
        session,
        confirm_plan=True,
    )


@router.post("/lesson/{content_id}/segments/{segment_id}/generate")
async def generate_lesson_segment(
    content_id: str,
    segment_id: str,
    payload: SegmentGenerate,
    request: Request,
    course: CurrentCourse,
    session: DbSession,
):
    content = get_content(session, "lesson", content_id, course.id)
    if content.version != payload.expected_version:
        raise HTTPException(409, "内容已被更新，请重新打开后生成")
    if not content.body.get("plan_confirmed", False):
        raise HTTPException(422, "请先确认课堂安排，再生成环节")
    body = deepcopy(content.body)
    index = next((i for i, part in enumerate(body["segments"]) if part["id"] == segment_id), None)
    if index is None:
        raise HTTPException(404, "当前讲义中不存在该环节")
    part = body["segments"][index]
    nodes = check_scope(session, "lesson", body, body["target_node_ids"], course.id)
    selected = [node for node in nodes if node.id in part["node_ids"]]
    result = retrieve(
        session,
        course.id,
        " ".join([part["title"], *[n.name for n in selected]]),
        part["node_ids"],
        "graph_augmented",
        budget=10,
    )
    missing = {item["node_id"] for item in result["node_evidence"] if not item["has_active_source"]}
    if missing:
        raise HTTPException(
            422,
            "以下知识点缺少有效原文依据：" + "、".join(n.name for n in selected if n.id in missing),
        )
    spec = {
        "lesson": lesson_plan(body),
        "segment": part,
        "segment_index": index,
        "nodes": [{"id": n.id, "name": n.name} for n in selected],
        "previous_context": [
            {"title": p["title"], "content": p["content"][-1000:]}
            for p in body["segments"][max(0, index - 2) : index]
        ],
        "examples": lesson_examples(session, {"segments": [part]}, course.id),
        "rewrite_instruction": payload.rewrite_instruction,
    }
    # 外部请求期间不持有数据库事务；返回后重新读取版本，避免覆盖并行编辑。
    title, target_ids = content.title, body["target_node_ids"]
    session.rollback()
    try:
        generated, info = await request.app.state.generation_provider.generate_lesson_segment(
            spec, result["evidence"]
        )
    except GenerationError as error:
        raise HTTPException(503, {"code": error.code, "message": str(error)}) from error
    content = get_content(session, "lesson", content_id, course.id)
    if content.version != payload.expected_version:
        raise HTTPException(409, "生成期间讲义已被修改，未覆盖新版本，请重新打开后再生成")
    body["segments"][index] = generated.segment.model_dump()
    if not body["preparation"]:
        body["preparation"] = generated.preparation
    if not body["homework"]:
        body["homework"] = generated.homework
    if not body.get("student_homework"):
        body["student_homework"] = generated.student_homework
    body["missing_info"] = list(dict.fromkeys([*body["missing_info"], *generated.missing_info]))
    content.generation_info = {
        **content.generation_info,
        "segments": {**content.generation_info.get("segments", {}), segment_id: info},
    }
    advance_revision(content)
    return write_content(
        content,
        TeachingWrite(
            title=title,
            target_node_ids=target_ids,
            body=LessonBody.model_validate(body),
        ),
        "lesson",
        course.id,
        session,
    )


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


def require_lesson_export(content_id, course, session, audience="teacher"):
    content = get_content(session, "lesson", content_id, course.id)
    if content.status != "approved" or content.reviewed_version != content.version:
        raise HTTPException(409, "仅可导出当前版本已审核的讲义")
    require_reviewable(content, session, course.id)
    if audience == "student" and any(
        "student_content" not in content.body["examples"][quiz_id]
        for quiz_id in linked_ids("lesson", content.body, "quiz_ids")
    ):
        raise HTTPException(409, "旧版题组快照尚无学生版题干，请重新保存并审核讲义")
    return content


@router.get("/lesson/{content_id}/print")
def validate_lesson_print(
    content_id: str,
    expected_version: int,
    course: CurrentCourse,
    session: DbSession,
    audience: Literal["teacher", "student"] = "teacher",
):
    content = require_lesson_export(content_id, course, session, audience)
    if content.version != expected_version:
        raise HTTPException(409, "讲义已更新，请重新打开预览后打印")
    return {"version": content.version}


@router.get("/lesson/{content_id}/word")
def lesson_word(
    content_id: str,
    course: CurrentCourse,
    session: DbSession,
    audience: Literal["teacher", "student"] = "teacher",
):
    content = require_lesson_export(content_id, course, session, audience)
    data = draft_data(content, session)
    nodes = session.scalars(
        select(KnowledgeNode).where(KnowledgeNode.id.in_(data["node_ids"]))
    ).all()
    materials = session.scalars(
        select(Material).where(Material.id.in_([c["material_id"] for c in data["citations"]]))
    ).all()
    try:
        output = export_lesson_word(
            content,
            data["citations"],
            {n.id: n.name for n in nodes},
            {m.id: m.storage_path for m in materials},
            audience=audience,
        )
    except LessonExportError as error:
        raise HTTPException(422, str(error)) from error
    return Response(
        output,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="lesson-{content.id}-{audience}.docx"'
        },
    )
