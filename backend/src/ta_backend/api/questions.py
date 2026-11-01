from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, or_, select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.models import (
    KnowledgeNode,
    Question,
    QuestionBatch,
    QuestionGroup,
    QuestionLink,
    QuestionPrediction,
    TeachingContent,
)
from ta_backend.services.matching import rank_question
from ta_backend.services.question_groups import similar_groups
from ta_backend.services.retrieval import retrieve

router = APIRouter(prefix="/courses/{course_id}", tags=["questions"])


class QuestionMatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question_text: str = Field(min_length=1, max_length=4000)
    method: Literal["auto", "name", "tfidf", "embedding", "mlp"] = "auto"
    max_suggestions: int = Field(default=3, ge=1, le=10)


def question_data(question: Question, session) -> dict:
    predictions = session.scalars(
        select(QuestionPrediction)
        .where(
            QuestionPrediction.question_id == question.id,
        )
        .order_by(QuestionPrediction.rank)
    ).all()
    links = session.scalars(
        select(QuestionLink).where(
            QuestionLink.question_id == question.id,
            QuestionLink.status == "confirmed",
        )
    ).all()
    return {
        "id": question.id,
        "batch_id": question.batch_id,
        "group_id": question.group_id,
        "text": question.text,
        "graph_version": question.graph_version,
        "model_version": question.model_version,
        "predictions": [
            {
                "node_id": prediction.node_id,
                "score": prediction.score,
                "rank": prediction.rank,
                "status": "predicted",
            }
            for prediction in predictions
        ],
        "confirmed_node_ids": [link.node_id for link in links],
        "score_semantics": "uncalibrated_relevance",
        "needs_review": question.links_status != "confirmed",
    }


def store_question(payload: QuestionMatch, course, session, local_matcher=None):
    nodes = session.scalars(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.course_id == course.id,
            KnowledgeNode.status == "confirmed",
            KnowledgeNode.kind != "chapter",
        )
        .order_by(KnowledgeNode.id)
    ).all()
    result = rank_question(
        payload.question_text,
        nodes,
        course,
        payload.method,
        local_matcher,
        limit=payload.max_suggestions,
    )
    ranked = [(hit.node_id, hit.score) for hit in result["matches"]]
    version = result["version"]
    question = Question(
        course_id=course.id,
        text=payload.question_text,
        graph_version=course.graph_version,
        model_version=version,
    )
    session.add(question)
    session.flush()
    session.add_all(
        QuestionPrediction(
            course_id=course.id,
            question_id=question.id,
            node_id=node_id,
            score=score,
            rank=index,
        )
        for index, (node_id, score) in enumerate(ranked[: payload.max_suggestions], 1)
    )
    session.flush()
    return question_data(question, session)


@router.post("/questions/match", status_code=201)
def match_question(
    payload: QuestionMatch, course: CurrentCourse, session: DbSession, request: Request
):
    result = store_question(payload, course, session, request.app.state.local_matcher)
    session.commit()
    return result


class BatchImport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(default="", max_length=120)
    questions: list[QuestionMatch] = Field(min_length=1, max_length=50)


@router.post("/questions/batch", status_code=201)
def import_questions(
    payload: BatchImport, course: CurrentCourse, session: DbSession, request: Request
):
    return save_batch(payload, course, session, request.app.state.local_matcher)["questions"]


@router.get("/questions")
def list_questions(course: CurrentCourse, session: DbSession, batch_id: str | None = None):
    query = select(Question).where(Question.course_id == course.id)
    if batch_id:
        scoped_get(session, QuestionBatch, batch_id, course.id)
        query = query.where(Question.batch_id == batch_id)
    questions = session.scalars(
        query.order_by(Question.created_at.desc(), Question.id).limit(100)
    ).all()
    return [question_data(question, session) for question in questions]


@router.get("/questions/{question_id}")
def read_question(question_id: str, course: CurrentCourse, session: DbSession):
    return question_data(scoped_get(session, Question, question_id, course.id), session)


@router.get("/nodes/{node_id}/questions")
def node_questions(node_id: str, course: CurrentCourse, session: DbSession):
    scoped_get(session, KnowledgeNode, node_id, course.id)
    predicted = select(QuestionPrediction.question_id).where(
        QuestionPrediction.course_id == course.id, QuestionPrediction.node_id == node_id
    )
    confirmed = select(QuestionLink.question_id).where(
        QuestionLink.course_id == course.id,
        QuestionLink.node_id == node_id,
        QuestionLink.status == "confirmed",
    )
    condition = (
        Question.course_id == course.id,
        or_(Question.id.in_(predicted), Question.id.in_(confirmed)),
    )
    total = session.scalar(select(func.count()).select_from(Question).where(*condition))
    questions = session.scalars(
        select(Question)
        .where(*condition)
        .order_by(Question.created_at.desc(), Question.id)
        .limit(50)
    ).all()
    items = []
    for question in questions:
        data = question_data(question, session)
        data["node_relation"] = (
            "confirmed"
            if node_id in data["confirmed_node_ids"]
            else "predicted"
            if data["needs_review"]
            else "not_selected"
        )
        items.append(data)
    return {"total": total, "items": items}


class ConfirmLinks(BaseModel):
    node_ids: list[str] = Field(max_length=10)


@router.post("/questions/{question_id}/links")
def confirm_links(
    question_id: str, payload: ConfirmLinks, course: CurrentCourse, session: DbSession
):
    question = scoped_get(session, Question, question_id, course.id)
    for node_id in payload.node_ids:
        scoped_get(session, KnowledgeNode, node_id, course.id)
    previous = set(
        session.scalars(
            select(QuestionLink.node_id).where(
                QuestionLink.question_id == question.id,
            )
        )
    )
    if question.links_status == "confirmed" and previous != set(payload.node_ids):
        for content in session.scalars(
            select(TeachingContent).where(
                TeachingContent.question_id == question.id,
                TeachingContent.course_id == course.id,
                TeachingContent.status == "approved",
            )
        ):
            content.status = "stale_review"
            content.reviewed_version = None
    session.execute(delete(QuestionLink).where(QuestionLink.question_id == question.id))
    session.add_all(
        QuestionLink(course_id=course.id, question_id=question.id, node_id=node_id)
        for node_id in dict.fromkeys(payload.node_ids)
    )
    question.links_status = "confirmed"
    session.commit()
    return question_data(question, session)


class RetrievalRequest(BaseModel):
    question_text: str = Field(min_length=1, max_length=4000)
    node_ids: list[str] = Field(default_factory=list, max_length=10)
    mode: Literal["basic", "graph_augmented"] = "basic"
    evidence_budget: int = Field(default=5, ge=1, le=10)


@router.post("/evidence/retrieve")
def retrieve_evidence(payload: RetrievalRequest, course: CurrentCourse, session: DbSession):
    for node_id in payload.node_ids:
        scoped_get(session, KnowledgeNode, node_id, course.id)
    return retrieve(
        session,
        course.id,
        payload.question_text,
        payload.node_ids,
        payload.mode,
        payload.evidence_budget,
    )


def batch_data(batch, session):
    questions = session.scalars(
        select(Question)
        .where(Question.course_id == batch.course_id, Question.batch_id == batch.id)
        .order_by(Question.batch_position, Question.created_at, Question.id)
    ).all()
    groups = session.scalars(
        select(QuestionGroup)
        .where(QuestionGroup.course_id == batch.course_id, QuestionGroup.batch_id == batch.id)
        .order_by(QuestionGroup.id)
    ).all()
    return {
        "id": batch.id,
        "title": batch.title,
        "created_at": batch.created_at,
        "grouping_version": batch.grouping_version,
        "question_count": len(questions),
        "similarity_threshold": batch.similarity_threshold,
        "questions": [question_data(q, session) for q in questions],
        "groups": [
            {
                "id": g.id,
                "title": g.title,
                "status": g.status,
                "version": g.version,
                "question_ids": [q.id for q in questions if q.group_id == g.id],
                "proposal": g.proposal,
            }
            for g in groups
        ],
    }


def save_batch(payload, course, session, local_matcher):
    batch = QuestionBatch(course_id=course.id, title=payload.title or "课堂提问")
    session.add(batch)
    session.flush()
    questions = []
    for position, item in enumerate(payload.questions, 1):
        result = store_question(item, course, session, local_matcher)
        question = session.get(Question, result["id"])
        question.batch_id = batch.id
        question.batch_position = position
        questions.append(question)
    for candidate in similar_groups([q.text for q in questions], batch.similarity_threshold):
        members = [questions[i] for i in candidate["indices"]]
        group = QuestionGroup(
            course_id=course.id,
            batch_id=batch.id,
            title=members[0].text[:200],
            proposal={
                "method": batch.grouping_version,
                "minimum_score": candidate["minimum_score"],
                "suggested_member_ids": [q.id for q in members],
            },
        )
        session.add(group)
        session.flush()
        for question in members:
            question.group_id = group.id
    session.commit()
    return batch_data(batch, session)


@router.post("/question-batches", status_code=201)
def create_batch(payload: BatchImport, course: CurrentCourse, session: DbSession, request: Request):
    return save_batch(payload, course, session, request.app.state.local_matcher)


@router.get("/question-batches")
def list_batches(course: CurrentCourse, session: DbSession):
    batches = session.scalars(
        select(QuestionBatch)
        .where(QuestionBatch.course_id == course.id)
        .order_by(QuestionBatch.created_at.desc(), QuestionBatch.id)
        .limit(50)
    ).all()
    ids = [b.id for b in batches]
    counts = dict(
        session.execute(
            select(Question.batch_id, func.count())
            .where(Question.course_id == course.id, Question.batch_id.in_(ids))
            .group_by(Question.batch_id)
        ).all()
    )
    return [
        {
            "id": b.id,
            "title": b.title,
            "created_at": b.created_at,
            "question_count": counts.get(b.id, 0),
        }
        for b in batches
    ]


@router.get("/question-batches/{batch_id}")
def read_batch(batch_id: str, course: CurrentCourse, session: DbSession):
    return batch_data(scoped_get(session, QuestionBatch, batch_id, course.id), session)


class GroupMembers(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(default="", max_length=200)
    question_ids: list[str] = Field(min_length=2, max_length=50)


def selected_members(ids, batch_id, course_id, session, group_id=None):
    unique = list(dict.fromkeys(ids))
    if len(unique) < 2:
        raise HTTPException(422, "分组至少需要两条不同的原问题")
    members = [scoped_get(session, Question, qid, course_id) for qid in unique]
    if any(q.batch_id != batch_id for q in members):
        raise HTTPException(409, "只能整理同一批次内的问题")
    if any(q.group_id and q.group_id != group_id for q in members):
        raise HTTPException(409, "问题已在其他组，请使用合并分组")
    return members


@router.post("/question-batches/{batch_id}/groups", status_code=201)
def create_group(batch_id: str, payload: GroupMembers, course: CurrentCourse, session: DbSession):
    batch = scoped_get(session, QuestionBatch, batch_id, course.id)
    members = selected_members(payload.question_ids, batch.id, course.id, session)
    group = QuestionGroup(
        course_id=course.id,
        batch_id=batch.id,
        title=payload.title or members[0].text[:200],
        status="confirmed",
        proposal={"method": "manual"},
    )
    session.add(group)
    session.flush()
    for question in members:
        question.group_id = group.id
    session.commit()
    return batch_data(batch, session)


class GroupUpdate(GroupMembers):
    expected_version: int = Field(ge=1)
    confirm: bool = True


def current_group(group_id, version, course_id, session):
    group = scoped_get(session, QuestionGroup, group_id, course_id)
    if group.version != version:
        raise HTTPException(409, "分组已被更新，请重新载入该批次")
    return group


@router.patch("/question-groups/{group_id}")
def update_group(group_id: str, payload: GroupUpdate, course: CurrentCourse, session: DbSession):
    group = current_group(group_id, payload.expected_version, course.id, session)
    members = selected_members(payload.question_ids, group.batch_id, course.id, session, group.id)
    for old in session.scalars(
        select(Question).where(Question.course_id == course.id, Question.group_id == group.id)
    ):
        old.group_id = None
    for question in members:
        question.group_id = group.id
    group.title = payload.title or members[0].text[:200]
    group.status = "confirmed" if payload.confirm else "candidate"
    group.version += 1
    session.commit()
    return batch_data(session.get(QuestionBatch, group.batch_id), session)


class MergeGroups(BaseModel):
    group_ids: list[str] = Field(min_length=2, max_length=25)
    expected_versions: dict[str, int] = Field(max_length=25)


@router.post("/question-groups/merge")
def merge_groups(payload: MergeGroups, course: CurrentCourse, session: DbSession):
    ids = list(dict.fromkeys(payload.group_ids))
    if len(ids) < 2 or set(ids) != set(payload.expected_versions):
        raise HTTPException(422, "请选择至少两个不同的分组，并提供各组版本")
    groups = [current_group(gid, payload.expected_versions[gid], course.id, session) for gid in ids]
    target = groups[0]
    if any(g.batch_id != target.batch_id for g in groups):
        raise HTTPException(409, "只能合并同一批次的分组")
    for question in session.scalars(
        select(Question).where(Question.course_id == course.id, Question.group_id.in_(ids))
    ):
        question.group_id = target.id
    target.status = "candidate"
    target.version += 1
    target.proposal = {"method": "manual-merge", "source_group_ids": ids}
    session.flush()
    for group in groups[1:]:
        session.delete(group)
    session.commit()
    return batch_data(session.get(QuestionBatch, target.batch_id), session)


@router.delete("/question-groups/{group_id}")
def dissolve_group(group_id: str, expected_version: int, course: CurrentCourse, session: DbSession):
    group = current_group(group_id, expected_version, course.id, session)
    batch = session.get(QuestionBatch, group.batch_id)
    for question in session.scalars(
        select(Question).where(Question.course_id == course.id, Question.group_id == group.id)
    ):
        question.group_id = None
    session.flush()
    session.delete(group)
    session.commit()
    return batch_data(batch, session)
