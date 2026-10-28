import argparse
import json
import random
from pathlib import Path


def read_pairs(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def split_families(pairs: list[dict], seed: int = 2026) -> dict[str, list[dict]]:
    """按人工指定 family_id 分组，不用文本哈希代替问题家族标注。"""
    families = sorted({pair["family_id"] for pair in pairs})
    random.Random(seed).shuffle(families)
    train_end, validation_end = int(len(families) * 0.7), int(len(families) * 0.85)
    family_sets = {
        "train": set(families[:train_end]),
        "validation": set(families[train_end:validation_end]),
        "test": set(families[validation_end:]),
    }
    return {
        split: [pair for pair in pairs if pair["family_id"] in group]
        for split, group in family_sets.items()
    }


def main():
    parser = argparse.ArgumentParser(description="先按问题家族划分，再开始正式训练")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    splits = split_families(read_pairs(args.input), args.seed)
    for split, rows in splits.items():
        (args.output / f"{split}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
    (args.output / "split.json").write_text(
        json.dumps(
            {
                "source": str(args.input),
                "seed": args.seed,
                "families": {
                    split: sorted({row["family_id"] for row in rows})
                    for split, rows in splits.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print({split: len(rows) for split, rows in splits.items()})


if __name__ == "__main__":
    main()
