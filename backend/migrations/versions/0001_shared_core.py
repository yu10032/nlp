"""共享课程、资料、图谱与教学内容表。"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "courses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_table(
        "materials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("material_id", sa.String(36), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("locator", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
    )
    op.create_table(
        "knowledge_nodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_table(
        "node_evidence",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("knowledge_nodes.id"), primary_key=True),
        sa.Column("chunk_id", sa.String(36), sa.ForeignKey("chunks.id"), primary_key=True),
    )
    op.create_table(
        "knowledge_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("knowledge_nodes.id"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("knowledge_nodes.id"), nullable=False),
        sa.Column("relation", sa.String(30), nullable=False),
        sa.Column("chunk_id", sa.String(36), sa.ForeignKey("chunks.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "teaching_contents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("reviewed_version", sa.Integer(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "content_nodes",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "content_id", sa.String(36), sa.ForeignKey("teaching_contents.id"), primary_key=True
        ),
        sa.Column("node_id", sa.String(36), sa.ForeignKey("knowledge_nodes.id"), primary_key=True),
    )
    op.create_table(
        "content_citations",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column(
            "content_id", sa.String(36), sa.ForeignKey("teaching_contents.id"), primary_key=True
        ),
        sa.Column("chunk_id", sa.String(36), sa.ForeignKey("chunks.id"), primary_key=True),
    )
    for table in (
        "materials",
        "chunks",
        "knowledge_nodes",
        "node_evidence",
        "knowledge_edges",
        "teaching_contents",
        "content_nodes",
        "content_citations",
    ):
        op.create_index(f"ix_{table}_course_id", table, ["course_id"])


def downgrade():
    for table in (
        "content_citations",
        "content_nodes",
        "teaching_contents",
        "knowledge_edges",
        "node_evidence",
        "knowledge_nodes",
        "chunks",
        "materials",
        "courses",
    ):
        op.drop_table(table)
