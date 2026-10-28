"""资料解析、问题关联与教学审核。"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    backfill_time = datetime.now(UTC).isoformat()
    op.add_column(
        "courses", sa.Column("graph_version", sa.Integer(), nullable=False, server_default="1")
    )
    for column in [
        sa.Column("document_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("filename", sa.String(255), nullable=False, server_default=""),
        sa.Column("storage_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="ready"),
        sa.Column("parser_version", sa.String(40), nullable=False, server_default="manual-v1"),
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=backfill_time,
        ),
    ]:
        op.add_column("materials", column)
    op.execute("UPDATE materials SET document_id = id")
    for column in [
        sa.Column("section_path", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("page_from", sa.Integer(), nullable=True),
        sa.Column("page_to", sa.Integer(), nullable=True),
        sa.Column("paragraph_locator", sa.String(100), nullable=True),
        sa.Column("extraction_status", sa.String(30), nullable=False, server_default="ok"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    ]:
        op.add_column("chunks", column)
    for column in [
        sa.Column("question_id", sa.String(36), nullable=True),
        sa.Column("generation_info", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=backfill_time,
        ),
    ]:
        op.add_column("teaching_contents", column)
    op.execute("UPDATE teaching_contents SET status = 'approved' WHERE status = 'reviewed'")
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("material_id", sa.String(36), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("family_id", sa.String(80), nullable=True),
        sa.Column("graph_version", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(80), nullable=False),
        sa.Column("links_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "question_predictions",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("knowledge_nodes.id"), primary_key=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
    )
    op.create_table(
        "question_links",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("questions.id"), primary_key=True),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("knowledge_nodes.id"), primary_key=True),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_table(
        "review_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "content_id", sa.String(36), sa.ForeignKey("teaching_contents.id"), nullable=False
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("reviewer", sa.String(80), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "content_revisions",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "content_id", sa.String(36), sa.ForeignKey("teaching_contents.id"), primary_key=True
        ),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for table in (
        "ingestion_jobs",
        "questions",
        "question_predictions",
        "question_links",
        "review_records",
        "content_revisions",
    ):
        op.create_index(f"ix_{table}_course_id", table, ["course_id"])


def downgrade():
    for table in (
        "content_revisions",
        "review_records",
        "question_links",
        "question_predictions",
        "questions",
        "ingestion_jobs",
    ):
        op.drop_table(table)
    for table, columns in {
        "teaching_contents": ["question_id", "generation_info", "updated_at"],
        "chunks": [
            "section_path",
            "page_from",
            "page_to",
            "paragraph_locator",
            "extraction_status",
            "position",
        ],
        "materials": [
            "document_id",
            "filename",
            "storage_path",
            "status",
            "parser_version",
            "warnings",
            "created_at",
        ],
        "courses": ["graph_version"],
    }.items():
        for column in columns:
            op.drop_column(table, column)
    op.execute("UPDATE teaching_contents SET status = 'reviewed' WHERE status = 'approved'")
