"""提问批次与可人工修订的相似分组。"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("questions", sa.Column("batch_position", sa.Integer(), nullable=True))
    op.create_table(
        "question_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("grouping_version", sa.String(50), nullable=False),
        sa.Column("similarity_threshold", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_question_batches_course_id", "question_batches", ["course_id"])
    op.create_table(
        "question_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("question_batches.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=False),
    )
    op.create_index("ix_question_groups_course_id", "question_groups", ["course_id"])
    op.create_index("ix_question_groups_batch_id", "question_groups", ["batch_id"])
    for column, target in (("batch_id", "question_batches"), ("group_id", "question_groups")):
        if op.get_bind().dialect.name == "sqlite":
            # SQLite 可直接增加可空引用列，避免重建已有问题及预测表。
            op.execute(
                f"ALTER TABLE questions ADD COLUMN {column} VARCHAR(36) REFERENCES {target}(id)"
            )
        else:
            op.add_column(
                "questions", sa.Column(column, sa.String(36), sa.ForeignKey(f"{target}.id"))
            )
        op.create_index(f"ix_questions_{column}", "questions", [column])


def downgrade():
    for column in ("group_id", "batch_id"):
        op.drop_index(f"ix_questions_{column}", table_name="questions")
        op.drop_column("questions", column)
    op.drop_column("questions", "batch_position")
    op.drop_table("question_groups")
    op.drop_table("question_batches")
