import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ta_backend.models import Chunk, KnowledgeEdge, KnowledgeNode, Material, NodeEvidence


def tokens(text: str) -> list[str]:
    terms = re.findall(r"[a-z0-9]+", text.casefold())
    for segment in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.extend(segment[index : index + 2] for index in range(len(segment) - 1))
    return terms


def tfidf_scores(query: str, texts: list[str]) -> list[float]:
    documents = [Counter(tokens(text)) for text in texts]
    query_counts = Counter(tokens(query))
    frequencies = Counter(term for document in documents for term in document)
    idf = {
        term: math.log((len(texts) + 1) / (count + 1)) + 1 for term, count in frequencies.items()
    }
    query_vector = {term: count * idf[term] for term, count in query_counts.items() if term in idf}
    query_norm = math.sqrt(sum(value**2 for value in query_vector.values()))
    scores = []
    for document in documents:
        vector = {term: (1 + math.log(count)) * idf[term] for term, count in document.items()}
        norm = math.sqrt(sum(value**2 for value in vector.values()))
        dot = sum(value * vector.get(term, 0) for term, value in query_vector.items())
        scores.append(dot / (query_norm * norm) if query_norm and norm else 0.0)
    return scores


def retrieve(
    session: Session,
    course_id: str,
    question: str,
    node_ids: list[str],
    mode: str = "basic",
    budget: int = 5,
) -> dict:
    rows = session.execute(
        select(Chunk, Material)
        .join(Material)
        .where(
            Chunk.course_id == course_id,
            Material.course_id == course_id,
            Material.active,
        )
        .order_by(Chunk.position, Chunk.id)
    ).all()
    scores = tfidf_scores(question, [chunk.text for chunk, _ in rows])
    selected = {
        chunk.id: (score, "retrieval") for (chunk, _), score in zip(rows, scores) if score > 0
    }
    if mode == "graph_augmented" and node_ids:
        confirmed = set(
            session.scalars(
                select(KnowledgeNode.id).where(
                    KnowledgeNode.id.in_(node_ids),
                    KnowledgeNode.course_id == course_id,
                    KnowledgeNode.status == "confirmed",
                )
            )
        )
        edges = session.scalars(
            select(KnowledgeEdge)
            .join(
                Chunk,
                Chunk.id == KnowledgeEdge.chunk_id,
            )
            .join(Material)
            .where(
                KnowledgeEdge.course_id == course_id,
                KnowledgeEdge.status == "confirmed",
                Chunk.course_id == course_id,
                Material.course_id == course_id,
                Material.active,
            )
        ).all()
        neighbors = set(confirmed)
        for edge in edges:
            if edge.source_id in confirmed:
                neighbors.add(edge.target_id)
            if edge.target_id in confirmed:
                neighbors.add(edge.source_id)
        valid_nodes = set(
            session.scalars(
                select(KnowledgeNode.id).where(
                    KnowledgeNode.id.in_(neighbors),
                    KnowledgeNode.course_id == course_id,
                    KnowledgeNode.status == "confirmed",
                )
            )
        )
        graph_chunks = set(
            session.scalars(
                select(NodeEvidence.chunk_id).where(
                    NodeEvidence.course_id == course_id,
                    NodeEvidence.node_id.in_(valid_nodes),
                )
            )
        )
        for chunk, _ in rows:
            if chunk.id in graph_chunks and chunk.id not in selected:
                selected[chunk.id] = (0.0, "graph")
    ranked = sorted(
        (row for row in rows if row[0].id in selected),
        key=lambda row: selected[row[0].id][0],
        reverse=True,
    )[:budget]
    evidence = [
        {
            "id": chunk.id,
            "material_id": material.id,
            "material_title": material.title,
            "material_version": material.version,
            "locator": chunk.locator,
            "section_path": chunk.section_path,
            "text": chunk.text,
            "score": round(selected[chunk.id][0], 4),
            "origin": selected[chunk.id][1],
        }
        for chunk, material in ranked
    ]
    return {
        "retrieval_version": "tfidf-bigram-v1",
        "mode": mode,
        "evidence": evidence,
        "missing_evidence": not evidence,
    }
