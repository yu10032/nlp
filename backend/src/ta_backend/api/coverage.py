from fastapi import APIRouter
from pydantic import BaseModel

from ta_backend.api.deps import CurrentCourse, DbSession
from ta_backend.services.coverage import calculate_coverage

router = APIRouter(prefix="/courses/{course_id}", tags=["coverage"])


class Metric(BaseModel):
    covered: int
    total: int
    ratio: float | None


class CoverageItem(BaseModel):
    node_id: str
    name: str
    material: bool
    quiz: bool
    lesson: bool


class CoverageRead(BaseModel):
    course_id: str
    metrics: dict[str, Metric]
    items: list[CoverageItem]


@router.get("/coverage", response_model=CoverageRead)
def read_coverage(course: CurrentCourse, session: DbSession):
    return calculate_coverage(session, course.id)
