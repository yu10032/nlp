import torch
from torch import Tensor, nn
from torch.nn import functional as F


class PairMatcher(nn.Module):
    """只训练匹配头；u、v 来自同一个冻结句编码器，输出二分类 logits。"""

    def __init__(self, embedding_dim: int, hidden_dim: int = 128, dropout: float = 0.1):
        super().__init__()
        self.head = nn.Sequential(
            nn.Linear(embedding_dim * 2 + 1, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, questions: Tensor, concepts: Tensor) -> Tensor:
        similarity = F.cosine_similarity(questions, concepts, dim=-1).unsqueeze(-1)
        features = torch.cat(
            [(questions - concepts).abs(), questions * concepts, similarity], dim=-1
        )
        return self.head(features).squeeze(-1)
