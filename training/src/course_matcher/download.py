"""单独执行的编码器下载步骤；训练、后端启动不自动下载。"""

import argparse
from pathlib import Path

from huggingface_hub import snapshot_download


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/encoders/bge-small-zh-v1.5"))
    args = parser.parse_args()
    snapshot_download(
        "BAAI/bge-small-zh-v1.5",
        local_dir=args.output,
        cache_dir=args.output.parent / ".cache",
        token=False,
        allow_patterns=[
            "modules.json",
            "config_sentence_transformers.json",
            "sentence_bert_config.json",
            "config.json",
            "tokenizer.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "1_Pooling/config.json",
            "model.safetensors",
        ],
    )
    print(f"编码器已保存：{args.output}")


if __name__ == "__main__":
    main()
