"""业务推理模块；不导入训练入口，不联网下载。"""

import json
import threading
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from course_matcher.evaluation import node_text
from course_matcher.model import PairMatcher


class LocalMatcher:
    def __init__(self, run_dir: Path, project_root: Path):
        self.run_dir = run_dir
        self.manifest = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        self.nodes = self.manifest["nodes"]
        self.node_ids = [n["id"] for n in self.nodes]
        torch.set_num_threads(4)
        self.encoder = SentenceTransformer(
            str(project_root / self.manifest["encoder_path"]), device="cpu", local_files_only=True
        )
        self.encoder.requires_grad_(False)
        self.encoder.eval()
        checkpoint = torch.load(run_dir / "best.pt", map_location="cpu", weights_only=True)
        self.head = PairMatcher(checkpoint["embedding_dim"], self.manifest["hidden_dim"], 0.0)
        self.head.load_state_dict(checkpoint["state_dict"])
        self.head.eval()
        self.vectors = self.encode([node_text(n) for n in self.nodes])
        self.lock = threading.Lock()

    def encode(self, texts):
        return self.encoder.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=32,
        )

    def score(self, question):
        with self.lock, torch.inference_mode():
            q = self.encode([question])[0]
            similarity = self.vectors @ q
            candidates = np.argsort(-similarity, kind="stable")[: self.manifest["candidate_k"]]
            queries = torch.from_numpy(np.repeat(q[None, :], len(candidates), axis=0))
            concepts = torch.from_numpy(self.vectors[candidates])
            values = torch.sigmoid(self.head(queries, concepts)).tolist()
            mlp = [-1.0] * len(self.nodes)
            for index, value in zip(candidates, values, strict=True):
                mlp[int(index)] = value
            return {"embedding": similarity.tolist(), "mlp": mlp}
