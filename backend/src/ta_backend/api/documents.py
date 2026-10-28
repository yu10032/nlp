from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.models import Chunk, IngestionJob, Material, new_id
from ta_backend.services.ingestion import ingest_material
from ta_backend.services.parsing import ParseError, validate_file

router = APIRouter(prefix="/courses/{course_id}", tags=["documents"])


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    title: str
    filename: str
    version: int
    active: bool
    status: str
    parser_version: str
    warnings: list[str]
    created_at: datetime
    chunk_count: int


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    material_id: str
    text: str
    locator: str
    section_path: list[str]
    page_from: int | None
    page_to: int | None
    paragraph_locator: str | None
    extraction_status: str
    position: int


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    material_id: str
    status: str
    error: str | None


@router.get("/documents", response_model=list[DocumentRead])
def list_documents(course: CurrentCourse, session: DbSession):
    rows = session.execute(
        select(Material, func.count(Chunk.id))
        .outerjoin(Chunk, Chunk.material_id == Material.id)
        .where(Material.course_id == course.id)
        .group_by(Material.id)
        .order_by(Material.created_at.desc(), Material.version.desc())
    )
    return [
        DocumentRead(
            **{
                key: getattr(material, key)
                for key in DocumentRead.model_fields
                if key != "chunk_count"
            },
            chunk_count=count,
        )
        for material, count in rows
    ]


@router.post("/documents", status_code=202)
async def upload_document(
    file: UploadFile,
    course: CurrentCourse,
    session: DbSession,
    request: Request,
    background_tasks: BackgroundTasks,
    replaces_id: str | None = None,
):
    settings = request.app.state.settings
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "文件超过 20 MB，请按章节拆分")
    filename = Path((file.filename or "").replace("\\", "/")).name
    try:
        suffix = validate_file(filename, content)
    except ParseError as error:
        raise HTTPException(415, str(error)) from error
    old = scoped_get(session, Material, replaces_id, course.id) if replaces_id else None
    material_id = new_id()
    folder = settings.storage_dir / course.id
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{material_id}{suffix}"
    path.write_bytes(content)
    version = 1
    if old:
        version = (
            session.scalar(
                select(func.max(Material.version)).where(
                    Material.course_id == course.id,
                    Material.document_id == old.document_id,
                )
            )
            + 1
        )
    material = Material(
        id=material_id,
        document_id=old.document_id if old else material_id,
        course_id=course.id,
        title=old.title if old else Path(filename).stem,
        filename=filename,
        storage_path=str(path),
        status="ingesting",
        active=False,
        version=version,
    )
    session.add(material)
    session.flush()
    job = IngestionJob(course_id=course.id, material_id=material.id)
    session.add(job)
    session.commit()
    background_tasks.add_task(ingest_material, job.id, request.app.state.session_factory)
    return {"job_id": job.id, "material_id": material.id, "status": "queued"}


@router.get("/jobs/{job_id}", response_model=JobRead)
def read_job(job_id: str, course: CurrentCourse, session: DbSession):
    return scoped_get(session, IngestionJob, job_id, course.id)


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkRead])
def read_chunks(document_id: str, course: CurrentCourse, session: DbSession):
    scoped_get(session, Material, document_id, course.id)
    return session.scalars(
        select(Chunk)
        .where(
            Chunk.material_id == document_id,
            Chunk.course_id == course.id,
        )
        .order_by(Chunk.position, Chunk.id)
    ).all()


@router.get("/documents/{document_id}/file")
def download_document(document_id: str, course: CurrentCourse, session: DbSession):
    material = scoped_get(session, Material, document_id, course.id)
    if not material.storage_path:
        raise HTTPException(404, "手工示例没有上传原文件")
    return FileResponse(material.storage_path, filename=material.filename)
