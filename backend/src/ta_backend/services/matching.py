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
