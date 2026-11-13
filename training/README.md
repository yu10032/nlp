# 离线匹配模型

已完成冻结中文句编码器、MLP 训练、验证集选阈值、问题级保留测试和本地后端加载。当前产物 `dev-nlp-001` 是开发模型，使用手写参考标签，尚未经组员独立复核。

## 在其他电脑复现

以下命令从 `work` 执行。训练依赖单独安装，轻量业务后端不必安装 PyTorch。下载目录由用户确认为项目内 `artifacts`，不在应用启动时下载。

```powershell
# 先安装 CPU PyTorch，再用已验证版本安装训练与推理依赖
.\.venv\Scripts\python.exe -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -c training/requirements.lock.txt -e ./training

# 显式下载公开的预训练编码器；不发送课程资料
.\.venv\Scripts\python.exe -m course_matcher.download

# 已有用户提供的原件及 nlp-curriculum 课程后，冻结当前节点范围
# 注意：再次执行 prepare 会重新输出开发问题和节点文件，应先保留已有人工编辑
.\.venv\Scripts\python.exe -m course_matcher.prepare

# 首次训练：已有 output_dir 不覆盖；重复实验须在 TOML 中使用新的 run_id/output_dir
.\.venv\Scripts\python.exe -m course_matcher.train --config training/configs/default.toml
```

编码器为 [BAAI/bge-small-zh-v1.5](https://huggingface.co/BAAI/bge-small-zh-v1.5)，固定参数，仅计算归一化向量。训练头输入为 `|u-v|`、`u*v` 和余弦相似度，使用带训练集正例权重的 BCE 损失、AdamW 和固定随机种子。所有候选节点都参与训练；推理时先用句向量召回 Top 5，再由匹配头重排，最多输出 3 个超过阈值的节点。

## 数据与划分

- `data/annotations/development-nlp-v1.jsonl`：184 条问题、68 个家族，含单节点、多节点和无关联情况，`label_status=development`。
- `data/annotations/curriculum-nodes-v1.json`：当前课程的 12 个已确认具体知识点、节点文字与图谱版本。章节节点不作为分类标签。
- 输入问题字段：`id/family_id/question/node_ids/label_status/reviewer/source/rationale`。`node_ids=[]` 表示无关联，不强行标正例。
- 同源改写共享 `family_id`，先按家族划分，再训练。当前训练 130 条、验证 24 条、测试 30 条；家族分别为 47/10/11，互不重叠。
- 换成正式数据时需人工核查标签和家族，填写审核人、使用新的数据版本，并建立独立的评价问题。不要只把开发数据的状态改名就当作正式实验。

独立复核可使用 `python -m course_matcher.review` 生成两份离线标注页面，汇总分歧后由第三人裁决；具体命令见[标注规则](../docs/annotation-guide.md)。页面不提供开发标签。复核后的手写题仍保留开发用途；独立评价使用未参与开发的脱敏真实课堂提问，带 `split_role=heldout` 的问题禁止重新划入训练与验证集。当前还没有已确认来源并完成复核的课堂保留集。

另有 16 条 `ai-supplement-nlp-v1.jsonl` 补充候选，尚未填写知识点标签，不能直接交给训练入口。先完成双人复核，再使用汇总后的 `questions.jsonl`；它们仍是 AI 编写的开发材料。

训练只更新 MLP 参数。编码器冻结，缓存验证和测试文本的向量不参与参数拟合。最佳权重由验证损失选择，阈值和自动方法由验证集 Micro F1 决定；固定后再运行保留测试。不要根据测试结果反复调整同一实验参数。

## 模型产物与接入

每次 run 保存 `best.pt`、`run.json`、`config.json`、`history.json`、`evaluation.json`、`split.json` 和各划分的问题快照。版本使用可读名称，不建立哈希清单。当前最佳权重是第 38 轮。

后端 `.env` 中填写：

```dotenv
TA_MATCHER_RUN_DIR=artifacts/matcher/dev-nlp-001
```

重启后端后加载一次本地编码器和匹配头。加载使用 `local_files_only=True`，不导入训练入口，不在线重训。配置目录错误或依赖未安装时启动会报错；清空这项即可使用轻量词面基线。

权重限定课程与冻结的图谱范围。课程不适用、节点内容或图谱版本变化时，界面会明确停用句向量/MLP选项，自动方式使用可用的 TF-IDF，明确记录真实方法。用户显式请求不可用的模型会收到 409。当前验证集选择 TF-IDF，MLP 仍可手动选择；不以“已训练”作为替换更好基线的理由。

新电脑上的模型文件需要单独复制或复现训练，Git 仓库不包含开发机权重和课程数据库。当前轻量 Docker 模板没有训练依赖及模型挂载，不宣称已完成容器内模型验收。

## 当前开发结果

`dev-nlp-001` 在 30 条开发保留问题上的 Micro F1 如下，标签尚未独立复核：

| 方法 | Micro F1 |
| --- | --- |
| 名称／别名 | 48.6% |
| TF-IDF | 73.0% |
| 固定句向量 | 52.5% |
| 自训 MLP | 54.5% |

验证集 TF-IDF 为 58.2%，MLP 为 57.6%，自动策略据此选择 TF-IDF。完整指标、阈值和错误案例以该 run 的 `evaluation.json`、`run.json` 为准；这些开发结果不作为正式课程效果结论。标注与独立评价要求见[标注规则](../docs/annotation-guide.md)。
