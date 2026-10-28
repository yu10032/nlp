from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ta_backend.models import Course


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


def get_course(course_id: str, session: DbSession) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


CurrentCourse = Annotated[Course, Depends(get_course)]


def scoped_get(session: Session, model, object_id: str, course_id: str):
    obj = session.get(model, object_id)
    if obj is None or obj.course_id != course_id:
        raise HTTPException(status_code=404, detail="当前课程中不存在该记录")
    return obj
