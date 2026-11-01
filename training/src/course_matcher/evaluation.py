"""问题级多标签指标；阈值只在验证集选择。"""

import math
import re
from collections import Counter


def node_text(node):
    return " ".join([node["name"], *node["aliases"], node["description"]])


def name_scores(question, nodes):
    return [
        float(any(s.casefold() in question.casefold() for s in [n["name"], *n["aliases"]]))
        for n in nodes
    ]


def tokens(text):
    terms = re.findall(r"[a-z0-9]+", text.casefold())
    for segment in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.extend(segment[i : i + 2] for i in range(len(segment) - 1))
    return terms


def lexical_scores(question, texts):
    documents = [Counter(tokens(t)) for t in texts]
    counts = Counter(tokens(question))
    df = Counter(term for doc in documents for term in doc)
    idf = {term: math.log((len(texts) + 1) / (count + 1)) + 1 for term, count in df.items()}
    query = {term: count * idf[term] for term, count in counts.items() if term in idf}
    norm = math.sqrt(sum(v * v for v in query.values()))
    result = []
    for doc in documents:
        vector = {term: (1 + math.log(count)) * idf[term] for term, count in doc.items()}
        dnorm = math.sqrt(sum(v * v for v in vector.values()))
        dot = sum(value * vector.get(term, 0) for term, value in query.items())
        result.append(dot / (norm * dnorm) if norm and dnorm else 0.0)
    return result


def predict(scores, node_ids, threshold, top_k=3):
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [node_ids[i] for i in ranked[:top_k] if scores[i] >= threshold]


def metrics(expected, predicted):
    tp = fp = fn = exact = no_match = false_links = 0
    for truth, guess in zip(expected, predicted, strict=True):
        a, b = set(truth), set(guess)
        tp += len(a & b)
        fp += len(b - a)
        fn += len(a - b)
        exact += a == b
        if not a:
            no_match += 1
            false_links += bool(b)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "questions": len(expected),
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "exact_match": exact / len(expected) if expected else None,
        "no_match_questions": no_match,
        "no_match_false_link_rate": false_links / no_match if no_match else None,
    }


def select_threshold(scores, rows, node_ids):
    expected = [r["node_ids"] for r in rows]
    choices = []
    for index in range(1, 100):
        threshold = index / 100
        result = metrics(expected, [predict(s, node_ids, threshold) for s in scores])
        choices.append((result["micro_f1"], result["exact_match"], threshold))
    return max(choices)[2]
