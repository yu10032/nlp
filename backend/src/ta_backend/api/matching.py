import json
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ta_backend.api.deps import CurrentCourse, DbSession
from ta_backend.models import KnowledgeNode
from ta_backend.services.matching import rank_question, scope_reason

router = APIRouter(prefix="/courses/{course_id}", tags=["matching"])


class MatchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)
    method: Literal["auto", "name", "tfidf", "embedding", "mlp"] = "name"


def nodes_for(session, course):
    return session.scalars(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.course_id == course.id,
            KnowledgeNode.status == "confirmed",
            KnowledgeNode.kind != "chapter",
        )
        .order_by(KnowledgeNode.id)
    ).all()


def matcher_info(local, course, nodes):
    reason = scope_reason(local, course, nodes)
    return {
        "active_method": "tfidf" if reason else local.manifest["preferred_method"],
        "scope_reason": reason,
        "run_id": local.manifest["run_id"] if local else None,
        "data_status": local.manifest["data_status"] if local else None,
        "methods": [
            {"id": m, "available": m in ("name", "tfidf") or not reason}
            for m in ("name", "tfidf", "embedding", "mlp")
        ],
    }


@router.post("/matches")
def match_nodes(payload: MatchRequest, course: CurrentCourse, session: DbSession, request: Request):
    result = rank_question(
        payload.question,
        nodes_for(session, course),
        course,
        payload.method,
        request.app.state.local_matcher,
    )
    return {**result, "method": result["version"], "method_id": result["method"]}


@router.get("/matcher")
def read_matcher(course: CurrentCourse, session: DbSession, request: Request):
    return matcher_info(request.app.state.local_matcher, course, nodes_for(session, course))


@router.post("/matches/compare")
def compare(payload: MatchRequest, course: CurrentCourse, session: DbSession, request: Request):
    local = request.app.state.local_matcher
    nodes = nodes_for(session, course)
    state = matcher_info(local, course, nodes)
    scores = local.score(payload.question) if not state["scope_reason"] else None
    results = [
        rank_question(payload.question, nodes, course, m["id"], local, scores)
        for m in state["methods"]
        if m["available"]
    ]
    return {"state": state, "results": results, "persisted": False}


@router.get("/experiments")
def read_experiment(course: CurrentCourse, session: DbSession, request: Request):
    local = request.app.state.local_matcher
    state = matcher_info(local, course, nodes_for(session, course))
    if state["scope_reason"]:
        return {"state": state, "run": None}

    def read(name):
        return json.loads((local.run_dir / name).read_text(encoding="utf-8"))

    info = local.manifest
    return {
        "state": state,
        "run": {
            k: info[k]
            for k in (
                "run_id",
                "encoder_id",
                "dataset_version",
                "data_status",
                "graph_version",
                "selected_epoch",
                "candidate_k",
                "seed",
                "train_seconds",
            )
        },
        "history": read("history.json"),
        "evaluation": read("evaluation.json"),
        "split": read("split.json"),
    }
