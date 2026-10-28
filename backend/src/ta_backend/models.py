"""首版共享数据对象；新增业务对象时再按业务拆分本模块。"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ta_backend.db import Base, UTCDateTime


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    graph_version: Mapped[int] = mapped_column(default=1)


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1)
    active: Mapped[bool] = mapped_column(default=True)
    document_id: Mapped[str] = mapped_column(String(36), default=new_id)
    filename: Mapped[str] = mapped_column(String(255), default="")
    storage_path: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="ready")
    parser_version: Mapped[str] = mapped_column(String(40), default="manual-v1")
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    locator: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    section_path: Mapped[list[str]] = mapped_column(JSON, default=list)
    page_from: Mapped[int | None] = mapped_column(default=None)
    page_to: Mapped[int | None] = mapped_column(default=None)
    paragraph_locator: Mapped[str | None] = mapped_column(String(100), default=None)
    extraction_status: Mapped[str] = mapped_column(String(30), default="ok")
    position: Mapped[int] = mapped_column(default=0)


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(30), default="concept")
    status: Mapped[str] = mapped_column(String(30), default="candidate")


class NodeEvidence(Base):
    __tablename__ = "node_evidence"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), primary_key=True)


class KnowledgeEdge(Base):
    __tablename__ = "knowledge_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"))
    target_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"))
    relation: Mapped[str] = mapped_column(String(30))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"))
    status: Mapped[str] = mapped_column(String(30), default="candidate")
    version: Mapped[int] = mapped_column(default=1)


class TeachingContent(Base):
    """答疑、题目、备课共享生命周期，具体内容结构由后续各业务 schema 定义。"""

    __tablename__ = "teaching_contents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    reviewed_version: Mapped[int | None] = mapped_column(default=None)
    archived: Mapped[bool] = mapped_column(default=False)
    question_id: Mapped[str | None] = mapped_column(String(36), default=None)
    generation_info: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ContentNode(Base):
    __tablename__ = "content_nodes"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("teaching_contents.id"), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), primary_key=True)


class ContentCitation(Base):
    __tablename__ = "content_citations"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("teaching_contents.id"), primary_key=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), primary_key=True)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    family_id: Mapped[str | None] = mapped_column(String(80), default=None)
    graph_version: Mapped[int] = mapped_column()
    model_version: Mapped[str] = mapped_column(String(80))
    links_status: Mapped[str] = mapped_column(String(30), default="predicted")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class QuestionPrediction(Base):
    __tablename__ = "question_predictions"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), primary_key=True)
    score: Mapped[float] = mapped_column()
    rank: Mapped[int] = mapped_column()


class QuestionLink(Base):
    __tablename__ = "question_links"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("knowledge_nodes.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(30), default="confirmed")


class ReviewRecord(Base):
    __tablename__ = "review_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("teaching_contents.id"))
    revision: Mapped[int] = mapped_column()
    result: Mapped[str] = mapped_column(String(30))
    reviewer: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class ContentRevision(Base):
    __tablename__ = "content_revisions"

    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), index=True)
    content_id: Mapped[str] = mapped_column(ForeignKey("teaching_contents.id"), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
