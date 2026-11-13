# 数据目录

- `sample/course.json`：手工编写的演示资料、节点和关系，用于验证工程接线；不是正式课程知识库。
- `annotations/example-pairs.jsonl`：6 个问题家族、12 个样本对，只展示标注格式，不能用于正式实验结论。
- `annotations/pilot-questions.jsonl`：24 条手工开发候选，尚未经标注者确认；规则见 `docs/annotation-guide.md`。
- `annotations/<dataset-version>/`：后续正式标注、划分与标注说明。
- `annotations/review-nlp-v1/`：本机生成的双人盲审页面、原始快照与回收记录，默认忽略；生成和汇总命令见 `docs/annotation-guide.md`。原始开发标签不会写入盲审页面。
- `annotations/ai-supplement-nlp-v1.jsonl`：按用户要求编写的 16 条 AI 补充候选，尚无人工标签，不是课堂实录，也不是独立测试集；使用 `review-ai-supplement-nlp-v1/` 中的 A/B 页面复核。
- `runtime/`：SQLite 数据库、上传文件与检索索引，不纳入源码管理。

正式问题使用人工确认的 `family_id`，同一问题的改写及全部正负样本对属于同一家族。
示例只有 6 个家族，因此划分比例只能近似 70/15/15。正式划分要在训练前冻结，并在实验记录中使用可读版本名。
