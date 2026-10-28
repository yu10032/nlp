from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.models import (
    KnowledgeNode,
    Question,
    QuestionLink,
    QuestionPrediction,
    TeachingContent,
)
from ta_backend.services.matching import NameMatcher
from ta_backend.services.retrieval import retrieve, tfidf_scores

router = APIRouter(prefix="/courses/{course_id}", tags=["questions"])


class QuestionMatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question_text: str = Field(min_length=1, max_length=4000)
    method: Literal["name", "tfidf"] = "tfidf"
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


@router.post("/questions/match", status_code=201)
def match_question(payload: QuestionMatch, course: CurrentCourse, session: DbSession):
    nodes = session.scalars(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.course_id == course.id,
            KnowledgeNode.status == "confirmed",
            KnowledgeNode.kind != "chapter",
        )
        .order_by(KnowledgeNode.id)
    ).all()
    if payload.method == "name":
        hits = NameMatcher().rank(payload.question_text, nodes)
        ranked = [(hit.node_id, hit.score) for hit in hits]
    else:
        texts = [" ".join([node.name, *node.aliases, node.description]) for node in nodes]
        scores = tfidf_scores(payload.question_text, texts)
        ranked = sorted(
            ((node.id, score) for node, score in zip(nodes, scores) if score >= 0.1),
            key=lambda item: item[1],
            reverse=True,
        )
    version = "name-baseline-v1" if payload.method == "name" else "tfidf-bigram-v1"
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
    session.commit()
    return question_data(question, session)


@router.get("/questions")
def list_questions(course: CurrentCourse, session: DbSession):
    questions = session.scalars(
        select(Question)
        .where(
            Question.course_id == course.id,
        )
        .order_by(Question.created_at.desc())
        .limit(100)
    ).all()
    return [question_data(question, session) for question in questions]


@router.get("/questions/{question_id}")
def read_question(question_id: str, course: CurrentCourse, session: DbSession):
    return question_data(scoped_get(session, Question, question_id, course.id), session)


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
