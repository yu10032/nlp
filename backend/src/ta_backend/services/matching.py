from dataclasses import dataclass
from typing import Protocol

from ta_backend.models import KnowledgeNode


@dataclass
class Match:
    node_id: str
    name: str
    score: float


class Matcher(Protocol):
    """C 成员训练模块的接入点，生产策略由验证集结果决定。"""

    version: str

    def rank(self, question: str, nodes: list[KnowledgeNode]) -> list[Match]: ...


class NameMatcher:
    """仅做名称/别名包含匹配，分数不是概率，也不是自训模型结果。"""

    version = "name-baseline-v1"

    def rank(self, question: str, nodes: list[KnowledgeNode]) -> list[Match]:
        question = question.casefold()
        return [
            Match(node.id, node.name, 1.0)
            for node in nodes
            if any(name.casefold() in question for name in [node.name, *node.aliases])
        ]


def scope_reason(local, course, nodes):
    if local is None:
        return "后端尚未配置本地匹配权重"
    info = local.manifest
    if info["course_id"] != course.id:
        return "当前课程不属于该模型的开发范围"
    if info["graph_version"] != course.graph_version:
        return "图谱版本已变化，请更新数据并重新训练"
    snapshot = [(n["id"], n["name"], n["aliases"], n["description"]) for n in info["nodes"]]
    current = [(n.id, n.name, n.aliases, n.description) for n in nodes]
    if snapshot != current:
        return "知识点集合已变化，请重新冻结模型范围"
    return ""


def rank_question(question, nodes, course, method="auto", local=None, local_scores=None, limit=3):
    from fastapi import HTTPException

    from ta_backend.services.retrieval import tfidf_scores

    reason = scope_reason(local, course, nodes)
    if method == "auto":
        method = local.manifest["preferred_method"] if not reason else "tfidf"
    if method in ("embedding", "mlp"):
        if reason:
            raise HTTPException(409, reason)
        values = (local_scores or local.score(question))[method]
        threshold = local.manifest["thresholds"][method]
        version = f"{local.manifest['run_id']}/{method}"
        hits = [
            Match(n.id, n.name, float(score))
            for n, score in zip(nodes, values, strict=True)
            if score >= threshold
        ]
    elif method == "name":
        hits = NameMatcher().rank(question, nodes)
        version = NameMatcher.version
        threshold = 0.5
    else:
        texts = [" ".join([n.name, *n.aliases, n.description]) for n in nodes]
        threshold = local.manifest["thresholds"]["tfidf"] if not reason else 0.1
        hits = [
            Match(n.id, n.name, float(s))
            for n, s in zip(nodes, tfidf_scores(question, texts), strict=True)
            if s >= threshold
        ]
        version = f"{local.manifest['run_id']}/tfidf" if not reason else "tfidf-bigram-v1"
    return {
        "method": method,
        "version": version,
        "threshold": threshold,
        "matches": sorted(hits, key=lambda h: h.score, reverse=True)[:limit],
    }
