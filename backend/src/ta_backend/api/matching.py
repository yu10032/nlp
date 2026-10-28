from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ta_backend.api.deps import CurrentCourse, DbSession
from ta_backend.models import KnowledgeNode
from ta_backend.services.matching import NameMatcher

router = APIRouter(prefix="/courses/{course_id}", tags=["matching"])


class MatchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)


class MatchRead(BaseModel):
    node_id: str
    name: str
    score: float


class MatchResult(BaseModel):
    method: str
    matches: list[MatchRead]


@router.post("/matches", response_model=MatchResult)
def match_nodes(payload: MatchRequest, course: CurrentCourse, session: DbSession):
    nodes = session.scalars(
        select(KnowledgeNode).where(
            KnowledgeNode.course_id == course.id,
            KnowledgeNode.status == "confirmed",
        )
    ).all()
    matcher = NameMatcher()
    return {"method": matcher.version, "matches": matcher.rank(payload.question, nodes)}
