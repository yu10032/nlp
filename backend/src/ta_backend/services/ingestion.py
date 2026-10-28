import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ta_backend.models import (
    Chunk,
    ContentCitation,
    Course,
    IngestionJob,
    KnowledgeEdge,
    Material,
    TeachingContent,
)
from ta_backend.services.parsing import PARSER_VERSION, ParseError, parse_file

logger = logging.getLogger(__name__)


def ingest_material(job_id: str, session_factory: sessionmaker):
    with session_factory() as session:
        job = session.get(IngestionJob, job_id)
        material = session.get(Material, job.material_id)
        job.status = "running"
        session.commit()
        try:
            result = parse_file(Path(material.storage_path))
            session.add_all(
                Chunk(
                    course_id=material.course_id,
                    material_id=material.id,
                    text=chunk.text,
                    locator=chunk.locator,
                    section_path=chunk.section_path,
                    page_from=chunk.page_from,
                    page_to=chunk.page_to,
                    paragraph_locator=chunk.paragraph_locator,
                    position=index,
                )
                for index, chunk in enumerate(result.chunks)
            )
            material.status = "partial" if result.warnings else "ready"
            material.parser_version = PARSER_VERSION
            material.warnings = result.warnings
            material.active = True
            previous = session.scalars(
                select(Material).where(
                    Material.document_id == material.document_id,
                    Material.id != material.id,
                    Material.course_id == material.course_id,
                    Material.active,
                )
            ).all()
            for old in previous:
                old.active = False
                invalidate_reviews(session, old.id, material.course_id)
                old_chunks = select(Chunk.id).where(Chunk.material_id == old.id)
                for edge in session.scalars(
                    select(KnowledgeEdge).where(
                        KnowledgeEdge.course_id == material.course_id,
                        KnowledgeEdge.chunk_id.in_(old_chunks),
                        KnowledgeEdge.status == "confirmed",
                    )
                ):
                    edge.status = "candidate"
                    edge.version += 1
                session.get(Course, material.course_id).graph_version += 1
            job.status = "done"
            session.commit()
        except ParseError as error:
            material.status = "failed"
            material.warnings = [str(error)]
            job.status = "failed"
            job.error = str(error)
            session.commit()
        except Exception:
            # 后台任务边界必须持久化失败；记录堆栈，不返回假成功或空索引。
            session.rollback()
            job = session.get(IngestionJob, job_id)
            material = session.get(Material, job.material_id)
            job.status = "failed"
            job.error = "解析出现错误，请检查文档或查看服务日志后重试"
            material.status = "failed"
            material.warnings = [job.error]
            session.commit()
            logger.exception("Document ingestion failed: %s", job_id)


def invalidate_reviews(session: Session, material_id: str, course_id: str):
    content_ids = (
        select(ContentCitation.content_id)
        .join(Chunk)
        .where(
            Chunk.material_id == material_id,
            ContentCitation.course_id == course_id,
        )
    )
    for content in session.scalars(
        select(TeachingContent).where(
            TeachingContent.id.in_(content_ids),
            TeachingContent.course_id == course_id,
            TeachingContent.status == "approved",
        )
    ):
        content.status = "stale_review"
        content.reviewed_version = None
