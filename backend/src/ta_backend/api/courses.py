from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ta_backend.api.deps import DbSession
from ta_backend.models import Course

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = ""


class CourseRead(CourseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str


@router.get("", response_model=list[CourseRead])
def list_courses(session: DbSession):
    return session.scalars(select(Course).order_by(Course.title)).all()


@router.post("", response_model=CourseRead, status_code=201)
def create_course(payload: CourseCreate, session: DbSession):
    course = Course(**payload.model_dump())
    session.add(course)
    session.commit()
    session.refresh(course)
    return course
