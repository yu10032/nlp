from sqlalchemy import select
from sqlalchemy.orm import Session

from ta_backend.models import (
    Chunk,
    ContentCitation,
    ContentNode,
    KnowledgeNode,
    Material,
    NodeEvidence,
    TeachingContent,
)


def calculate_coverage(session: Session, course_id: str) -> dict:
    nodes = session.scalars(
        select(KnowledgeNode)
        .where(
            KnowledgeNode.course_id == course_id,
            KnowledgeNode.status == "confirmed",
            KnowledgeNode.kind != "chapter",
        )
        .order_by(KnowledgeNode.name)
    ).all()
    material_nodes = set(
        session.scalars(
            select(NodeEvidence.node_id)
            .join(Chunk)
            .join(Material)
            .where(
                NodeEvidence.course_id == course_id,
                Chunk.course_id == course_id,
                Material.course_id == course_id,
                Material.active,
            )
        )
    )
    # 任何引用失效，整个内容先退出正式覆盖，等待后续重新审核。
    invalid_citations = (
        select(ContentCitation.content_id)
        .join(Chunk)
        .join(Material)
        .where(ContentCitation.course_id == course_id, Material.active.is_(False))
    )
    reviewed = session.execute(
        select(ContentNode.node_id, TeachingContent.kind)
        .join(TeachingContent, TeachingContent.id == ContentNode.content_id)
        .where(
            ContentNode.course_id == course_id,
            TeachingContent.course_id == course_id,
            TeachingContent.status == "approved",
            TeachingContent.archived.is_(False),
            TeachingContent.reviewed_version == TeachingContent.version,
            TeachingContent.id.not_in(invalid_citations),
        )
    ).all()
    content_nodes = {
        kind: {node_id for node_id, content_kind in reviewed if content_kind == kind}
        for kind in ("quiz", "lesson")
    }
    items = [
        {
            "node_id": node.id,
            "name": node.name,
            "material": node.id in material_nodes,
            "quiz": node.id in content_nodes["quiz"],
            "lesson": node.id in content_nodes["lesson"],
        }
        for node in nodes
    ]
    total = len(nodes)
    metrics = {}
    for key in ("material", "quiz", "lesson"):
        covered = sum(item[key] for item in items)
        metrics[key] = {
            "covered": covered,
            "total": total,
            "ratio": covered / total if total else None,
        }
    return {"course_id": course_id, "metrics": metrics, "items": items}
