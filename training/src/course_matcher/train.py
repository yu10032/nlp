"""显式离线训练与保留测试；后端不导入此入口。"""

import argparse
import json
import random
import time
import tomllib
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from course_matcher.data import read_pairs, split_families
from course_matcher.evaluation import (
    lexical_scores,
    metrics,
    name_scores,
    node_text,
    predict,
    select_threshold,
)
from course_matcher.model import PairMatcher


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_training(config):
    random.seed(config["seed"])
    np.random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    torch.set_num_threads(4)
    rows = read_pairs(Path(config["dataset_file"]))
    snapshot = json.loads(Path(config["nodes_file"]).read_text(encoding="utf-8"))
    nodes = snapshot["nodes"]
    node_ids = [n["id"] for n in nodes]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("问题 ID 重复")
    for row in rows:
        if row["label_status"] == "confirmed" and not row.get("reviewer", "").strip():
            raise ValueError(f"已确认标注缺少审核人：{row['id']}")
        if not row["family_id"] or not set(row["node_ids"]).issubset(node_ids):
            raise ValueError(f"问题家族或知识点标签无效：{row['id']}")
    splits = split_families(rows, config["seed"])
    if any(not values for values in splits.values()):
        raise ValueError("需要更多独立问题家族才能划分训练、验证和测试集")
    if (
        any(r["label_status"] != "confirmed" for r in rows)
        and config["data_status"] != "development"
    ):
        raise ValueError("正式训练只接受已核查标注；开发样本须标记 data_status=development")
    output = Path(config["output_dir"])
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "config.json", config)
    write_json(
        output / "split.json",
        {
            k: {"questions": len(v), "families": sorted({r["family_id"] for r in v})}
            for k, v in splits.items()
        },
    )
    for key, items in splits.items():
        (output / f"{key}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items), encoding="utf-8"
        )
    encoder = SentenceTransformer(config["encoder_path"], device="cpu", local_files_only=True)
    encoder.requires_grad_(False)
    encoder.eval()
    texts = list(dict.fromkeys([r["question"] for r in rows] + [node_text(n) for n in nodes]))
    print(f"编码 {len(texts)} 段文本；编码器冻结，仅训练匹配头", flush=True)
    vectors = encoder.encode(
        texts, batch_size=32, normalize_embeddings=True, show_progress_bar=True
    )
    cache = dict(zip(texts, vectors, strict=True))
    concepts = np.stack([cache[node_text(n)] for n in nodes])

    def dataset(items):
        q = np.stack([cache[r["question"]] for r in items])
        labels = np.array(
            [[float(n in r["node_ids"]) for n in node_ids] for r in items], dtype=np.float32
        )
        return TensorDataset(
            torch.from_numpy(np.repeat(q, len(nodes), axis=0)),
            torch.from_numpy(np.tile(concepts, (len(items), 1))),
            torch.from_numpy(labels.flatten()),
        )

    train = dataset(splits["train"])
    validation = dataset(splits["validation"])
    loader = DataLoader(train, batch_size=config["batch_size"], shuffle=True)
    model = PairMatcher(concepts.shape[1], config["hidden_dim"], config["dropout"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"], weight_decay=0.01)
    positives = train.tensors[-1].sum()
    if positives == 0:
        raise ValueError("训练集缺少正例")
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=(len(train) - positives) / positives)
    best_loss = float("inf")
    history = []
    start = time.perf_counter()
    for epoch in range(1, config["epochs"] + 1):
        model.train()
        total = 0.0
        for questions, target, labels in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(questions, target), labels)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(labels)
        model.eval()
        with torch.inference_mode():
            vloss = loss_fn(
                model(validation.tensors[0], validation.tensors[1]), validation.tensors[2]
            ).item()
        row = {"epoch": epoch, "train_loss": total / len(train), "validation_loss": vloss}
        history.append(row)
        if vloss < best_loss:
            best_loss = vloss
            torch.save(
                {
                    "state_dict": model.state_dict(),
                    "embedding_dim": concepts.shape[1],
                    "epoch": epoch,
                },
                output / "best.pt",
            )
        if epoch == 1 or epoch % 10 == 0:
            print(row, flush=True)
    write_json(output / "history.json", history)
    checkpoint = torch.load(output / "best.pt", map_location="cpu", weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    def score(items):
        result = {m: [] for m in ("name", "tfidf", "embedding", "mlp")}
        for row in items:
            q = cache[row["question"]]
            similarity = concepts @ q
            candidates = np.argsort(-similarity, kind="stable")[: config["candidate_k"]]
            with torch.inference_mode():
                values = torch.sigmoid(
                    model(
                        torch.from_numpy(np.repeat(q[None, :], len(candidates), axis=0)),
                        torch.from_numpy(concepts[candidates]),
                    )
                ).tolist()
            mlp = [-1.0] * len(nodes)
            for index, value in zip(candidates, values, strict=True):
                mlp[int(index)] = value
            result["name"].append(name_scores(row["question"], nodes))
            result["tfidf"].append(lexical_scores(row["question"], [node_text(n) for n in nodes]))
            result["embedding"].append(similarity.tolist())
            result["mlp"].append(mlp)
        return result

    val_scores = score(splits["validation"])
    thresholds = {
        m: (0.5 if m == "name" else select_threshold(s, splits["validation"], node_ids))
        for m, s in val_scores.items()
    }
    validation_metrics = {
        method: metrics(
            [r["node_ids"] for r in splits["validation"]],
            [predict(v, node_ids, thresholds[method]) for v in values],
        )
        for method, values in val_scores.items()
    }
    preferred_method = max(validation_metrics, key=lambda m: validation_metrics[m]["micro_f1"])
    # 测试集仅在权重、阈值与候选预算固定后运行，不用于重选参数。
    test_scores = score(splits["test"])
    evaluation = {
        "data_status": config["data_status"],
        "threshold_source": "validation",
        "methods": {},
        "errors": [],
    }
    truth = [r["node_ids"] for r in splits["test"]]
    for method, values in test_scores.items():
        guesses = [predict(s, node_ids, thresholds[method]) for s in values]
        evaluation["methods"][method] = {**metrics(truth, guesses), "threshold": thresholds[method]}
        evaluation["errors"].extend(
            {"method": method, "question": r["question"], "expected": a, "predicted": b}
            for r, a, b in zip(splits["test"], truth, guesses, strict=True)
            if set(a) != set(b)
        )
    positives = sum(len(r["node_ids"]) for r in splits["test"])
    recalled = sum(
        len(set(predict(s, node_ids, -1.0, config["candidate_k"])) & set(r["node_ids"]))
        for s, r in zip(test_scores["embedding"], splits["test"], strict=True)
    )
    evaluation["candidate_recall"] = {
        "k": config["candidate_k"],
        "ratio": recalled / positives if positives else None,
    }
    evaluation["validation_methods"] = validation_metrics
    write_json(output / "evaluation.json", evaluation)
    manifest = {
        "preferred_method": preferred_method,
        "run_id": config["run_id"],
        "data_status": config["data_status"],
        "dataset_version": config["dataset_version"],
        "course_id": snapshot["course_id"],
        "graph_version": snapshot["graph_version"],
        "nodes": nodes,
        "encoder_id": config["encoder"],
        "encoder_path": config["encoder_path"],
        "hidden_dim": config["hidden_dim"],
        "thresholds": thresholds,
        "candidate_k": config["candidate_k"],
        "selected_epoch": checkpoint["epoch"],
        "seed": config["seed"],
        "train_seconds": round(time.perf_counter() - start, 2),
    }
    write_json(output / "run.json", manifest)
    print(json.dumps(evaluation["methods"], ensure_ascii=False, indent=2), flush=True)
    print(f"已保存真实权重与保留测试结果：{output}；数据状态：{config['data_status']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("training/configs/default.toml"))
    args = parser.parse_args()
    run_training(tomllib.loads(args.config.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
