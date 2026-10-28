from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from ta_backend.api.deps import CurrentCourse, DbSession, scoped_get
from ta_backend.models import Chunk, KnowledgeEdge, KnowledgeNode, Material, NodeEvidence

router = APIRouter(prefix="/courses/{course_id}", tags=["graph"])


class NodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    aliases: list[str]
    description: str
    kind: str
    status: str


class EdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_id: str
    target_id: str
    relation: str
    chunk_id: str
    status: str
    version: int


class GraphRead(BaseModel):
    version: int
    nodes: list[NodeRead]
    edges: list[EdgeRead]


class EvidenceRead(BaseModel):
    id: str
    material_id: str
    material_title: str
    material_version: int
    locator: str
    text: str


class NodeDetail(NodeRead):
    evidence: list[EvidenceRead]


@router.get("/graph", response_model=GraphRead)
def read_graph(course: CurrentCourse, session: DbSession):
    nodes = session.scalars(select(KnowledgeNode).where(KnowledgeNode.course_id == course.id)).all()
    edges = session.scalars(select(KnowledgeEdge).where(KnowledgeEdge.course_id == course.id)).all()
    return {"version": course.graph_version, "nodes": nodes, "edges": edges}


@router.get("/nodes/{node_id}", response_model=NodeDetail)
def read_node(node_id: str, course: CurrentCourse, session: DbSession):
    node = session.scalar(
        select(KnowledgeNode).where(
            KnowledgeNode.id == node_id,
            KnowledgeNode.course_id == course.id,
        )
    )
    if node is None:
        raise HTTPException(status_code=404, detail="当前课程中没有该知识点")
    rows = session.execute(
        select(Chunk, Material)
        .join(NodeEvidence, NodeEvidence.chunk_id == Chunk.id)
        .join(Material, Material.id == Chunk.material_id)
        .where(
            NodeEvidence.node_id == node.id,
            NodeEvidence.course_id == course.id,
            Chunk.course_id == course.id,
            Material.course_id == course.id,
            Material.active,
        )
    )
    evidence = [
        EvidenceRead(
            id=chunk.id,
            material_id=material.id,
            material_title=material.title,
            material_version=material.version,
            locator=chunk.locator,
            text=chunk.text,
        )
        for chunk, material in rows
    ]
    return NodeDetail(**NodeRead.model_validate(node).model_dump(), evidence=evidence)


class NodeWrite(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default="", max_length=3000)
    kind: Literal["chapter", "concept", "method", "algorithm", "model", "task", "metric"] = (
        "concept"
    )
    status: Literal["candidate", "confirmed"] = "candidate"
    evidence_chunk_ids: list[str] = Field(default_factory=list, max_length=20)


def checked_chunks(session, ids: list[str], course_id: str) -> list[Chunk]:
    chunks = session.scalars(
        select(Chunk)
        .join(Material)
        .where(
            Chunk.id.in_(ids),
            Chunk.course_id == course_id,
            Material.course_id == course_id,
            Material.active,
        )
    ).all()
    if len(chunks) != len(set(ids)):
        raise HTTPException(422, "引用包含其他课程或失效的片段，请重新选择")
    return chunks


def write_node(node, payload: NodeWrite, course, session):
    existing = session.scalars(
        select(KnowledgeNode).where(
            KnowledgeNode.course_id == course.id,
            KnowledgeNode.id != node.id,
        )
    ).all()
    if any(other.name.casefold() == payload.name.casefold() for other in existing):
        raise HTTPException(409, "课程内已有同名知识点，请编辑现有节点")
    chunks = checked_chunks(session, payload.evidence_chunk_ids, course.id)
    if payload.status == "confirmed" and not chunks:
        raise HTTPException(422, "确认知识点前请关联至少一段有效课程资料")
    for key, value in payload.model_dump(exclude={"evidence_chunk_ids"}).items():
        setattr(node, key, value)
    session.add(node)
    session.flush()
    from sqlalchemy import delete

    session.execute(delete(NodeEvidence).where(NodeEvidence.node_id == node.id))
    session.add_all(
        NodeEvidence(course_id=course.id, node_id=node.id, chunk_id=chunk.id) for chunk in chunks
    )
    course.graph_version += 1
    session.commit()
    return read_node(node.id, course, session)


@router.post("/nodes", response_model=NodeDetail, status_code=201)
def create_node(payload: NodeWrite, course: CurrentCourse, session: DbSession):
    node = KnowledgeNode(course_id=course.id)
    return write_node(node, payload, course, session)


@router.patch("/nodes/{node_id}", response_model=NodeDetail)
def update_node(node_id: str, payload: NodeWrite, course: CurrentCourse, session: DbSession):
    node = scoped_get(session, KnowledgeNode, node_id, course.id)
    return write_node(node, payload, course, session)


class EdgeWrite(BaseModel):
    source_id: str
    target_id: str
    relation: Literal["contains", "uses", "applies_to", "contrasts_with", "prerequisite_of"]
    chunk_id: str


class EdgeReview(BaseModel):
    result: Literal["confirmed", "rejected"]


@router.post("/edges", response_model=EdgeRead, status_code=201)
def create_edge(payload: EdgeWrite, course: CurrentCourse, session: DbSession):
    for node_id in (payload.source_id, payload.target_id):
        scoped_get(session, KnowledgeNode, node_id, course.id)
    if payload.source_id == payload.target_id:
        raise HTTPException(422, "关系的起点与终点不能相同")
    checked_chunks(session, [payload.chunk_id], course.id)
    duplicate = session.scalar(
        select(KnowledgeEdge).where(
            KnowledgeEdge.course_id == course.id,
            KnowledgeEdge.source_id == payload.source_id,
            KnowledgeEdge.target_id == payload.target_id,
            KnowledgeEdge.relation == payload.relation,
            KnowledgeEdge.status != "rejected",
        )
    )
    if duplicate:
        raise HTTPException(409, "已存在相同关系")
    edge = KnowledgeEdge(course_id=course.id, **payload.model_dump())
    session.add(edge)
    course.graph_version += 1
    session.commit()
    return edge


@router.post("/edges/{edge_id}/review", response_model=EdgeRead)
def review_edge(edge_id: str, payload: EdgeReview, course: CurrentCourse, session: DbSession):
    edge = scoped_get(session, KnowledgeEdge, edge_id, course.id)
    if payload.result == "confirmed":
        checked_chunks(session, [edge.chunk_id], course.id)
        for node_id in (edge.source_id, edge.target_id):
            node = scoped_get(session, KnowledgeNode, node_id, course.id)
            if node.status != "confirmed":
                raise HTTPException(422, "请先确认关系两端的知识点")
        if edge.relation == "prerequisite_of":
            edges = session.scalars(
                select(KnowledgeEdge).where(
                    KnowledgeEdge.course_id == course.id,
                    KnowledgeEdge.status == "confirmed",
                    KnowledgeEdge.relation == "prerequisite_of",
                    KnowledgeEdge.id != edge.id,
                )
            ).all()
            stack, visited = [edge.target_id], set()
            while stack:
                current = stack.pop()
                if current == edge.source_id:
                    raise HTTPException(422, "这条先修关系会形成循环，请调整方向或节点")
                if current not in visited:
                    visited.add(current)
                    stack.extend(item.target_id for item in edges if item.source_id == current)
    edge.status = payload.result
    edge.version += 1
    course.graph_version += 1
    session.commit()
    return edge
