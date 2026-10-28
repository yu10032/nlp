"""离线训练入口；正式评测与后端权重加载在后续迭代接入。"""

import argparse
import json
import random
import tomllib
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from course_matcher.data import read_pairs
from course_matcher.model import PairMatcher


def encode_pairs(path: Path, encoder: SentenceTransformer) -> TensorDataset:
    pairs = read_pairs(path)
    questions = encoder.encode([row["question"] for row in pairs], convert_to_tensor=True)
    concepts = encoder.encode([row["node_text"] for row in pairs], convert_to_tensor=True)
    labels = torch.tensor([row["label"] for row in pairs], dtype=torch.float32)
    return TensorDataset(questions.cpu(), concepts.cpu(), labels)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("training/configs/default.toml"))
    args = parser.parse_args()
    config = tomllib.loads(args.config.read_text(encoding="utf-8"))
    random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    output = Path(config["output_dir"])
    # 每次实验独立目录，避免新实验覆盖旧权重和日志。
    output.mkdir(parents=True, exist_ok=False)
    encoder = SentenceTransformer(
        config["encoder"], cache_folder=config["encoder_cache"], device="cpu"
    )
    encoder.requires_grad_(False)
    encoder.eval()
    train = encode_pairs(Path(config["train_file"]), encoder)
    validation = encode_pairs(Path(config["validation_file"]), encoder)
    loader = DataLoader(train, batch_size=config["batch_size"], shuffle=True)
    dimension = train.tensors[0].shape[1]
    model = PairMatcher(dimension, config["hidden_dim"], config["dropout"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=config["learning_rate"])
    loss_fn = nn.BCEWithLogitsLoss()
    best_loss = float("inf")
    (output / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "history.jsonl").open("w", encoding="utf-8") as history:
        for epoch in range(1, config["epochs"] + 1):
            model.train()
            total_loss = 0.0
            for questions, concepts, labels in loader:
                optimizer.zero_grad()
                loss = loss_fn(model(questions, concepts), labels)
                loss.backward()
                optimizer.step()
                total_loss += loss.item() * len(labels)
            model.eval()
            with torch.no_grad():
                questions, concepts, labels = validation.tensors
                validation_loss = loss_fn(model(questions, concepts), labels).item()
            row = {
                "epoch": epoch,
                "train_loss": total_loss / len(train),
                "validation_loss": validation_loss,
            }
            history.write(json.dumps(row) + "\n")
            history.flush()
            print(row)
            if validation_loss < best_loss:
                best_loss = validation_loss
                torch.save(
                    {
                        "state_dict": model.state_dict(),
                        "embedding_dim": dimension,
                        "config": config,
                        "epoch": epoch,
                    },
                    output / "best.pt",
                )


if __name__ == "__main__":
    main()
