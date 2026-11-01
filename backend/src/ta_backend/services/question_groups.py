"""仅根据问题文本提出候选，不以知识点相同替代问题诉求相同。"""

import math
from collections import Counter

from ta_backend.services.retrieval import tokens


def similar_groups(texts: list[str], threshold: float = 0.6) -> list[dict]:
    documents = [Counter(tokens(text)) for text in texts]
    frequency = Counter(term for doc in documents for term in doc)
    idf = {term: math.log((len(texts) + 1) / (count + 1)) + 1 for term, count in frequency.items()}
    vectors = []
    for doc in documents:
        vector = {term: (1 + math.log(count)) * idf[term] for term, count in doc.items()}
        norm = math.sqrt(sum(v * v for v in vector.values()))
        vectors.append({term: v / norm for term, v in vector.items()} if norm else {})
    scores = {
        (i, j): sum(v * vectors[j].get(term, 0) for term, v in vectors[i].items())
        for i in range(len(texts))
        for j in range(i + 1, len(texts))
    }
    groups = [[i] for i in range(len(texts))]
    # 完全链接：组内任意两问都过阈值，避免 A≈B、B≈C 造成不相似的 A/C 被串联。
    for (i, j), score in sorted(scores.items(), key=lambda item: (-item[1], item[0])):
        if score < threshold:
            break
        left = next(g for g in groups if i in g)
        right = next(g for g in groups if j in g)
        if left is right:
            continue
        if all(scores[tuple(sorted((a, b)))] >= threshold for a in left for b in right):
            left.extend(right)
            left.sort()
            groups.remove(right)
    return [
        {
            "indices": g,
            "minimum_score": round(min(scores[(a, b)] for a in g for b in g if a < b), 4),
        }
        for g in groups
        if len(g) > 1
    ]
