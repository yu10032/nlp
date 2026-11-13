# 标注规则

## 当前数据

| 文件（位于 `data/annotations/`） | 用途 |
| --- | --- |
| `pilot-questions.jsonl` | 24 条早期开发候选；使用 `suggested_node_ids/confirmed_node_ids/annotation_status` |
| `development-nlp-v1.jsonl` | 184 条手写开发问题、68 个家族；使用 `node_ids/label_status/reviewer` |
| `curriculum-nodes-v1.json` | 知识体系课程 12 个已确认具体节点的冻结快照 |

两套问题格式分别使用，不混用。开发标签尚未独立复核；当前训练结果及复现见[训练说明](../training/README.md)。

## 判定与复核

1. 只标记回答问题必需、语义明确相关的知识点；允许多标签和零标签。
2. 同名、同章节或图上相邻不必然相关；核查困难负例与未出现节点原名的表达。
3. 考试时间、评分和通知等问题不强行挂到课程节点；模型建议不能直接作为金标准。
4. 独立核查问题、节点和 `family_id`，填写复核人及理由，保留分歧及解决结果。正式数据另建版本，不只批量改状态。

## 划分与评价

同一原问题的改写与所有正负配对共享 `family_id`。先按家族划分，再拟合、训练和选择阈值；独立保留未参与开发的评价问题。固定图谱、资料、编码器和候选预算，分别评价候选召回、排序、多标签结果与无关联误挂。

阈值和自动策略使用验证集选择，测试集只在冻结后运行；新数据或新方案使用独立 run。检索评价记录片段相关性、遗漏与一跳补充噪声，自动化测试中的评价文字不作为教师结论。

## 离线双人复核

`course_matcher.review` 生成可以直接用浏览器打开的离线页面，无需启动服务、联网或加载模型。页面包含冻结的知识点定义与有效原文，不提供开发标签或模型预测。两位组员分别填写 A、B；负责人保留原始数据，收回记录后比较分歧。家族原编号作为候选提供，仍须逐题核查，同源问题的编号需要统一。

从 `work` 执行，输出目录必须使用新名称，已有目录不会被覆盖：

```powershell
.\.venv\Scripts\python.exe -m course_matcher.review prepare `
  --input data/annotations/development-nlp-v1.jsonl `
  --nodes data/annotations/curriculum-nodes-v1.json `
  --dataset-version development-nlp-v1 `
  --output data/annotations/review-nlp-v1
```

分别将 `review-a.html`、`review-b.html` 交给两名独立复核人，只需各自一份 HTML。不要将带原标签的 `original.jsonl` 作为盲审资料发放。复核包和正式课堂数据默认不纳入 Git。

每位复核人按以下顺序操作：

1. 填写自己的实际姓名或组内唯一编号，阅读右侧定义和原文。
2. 选择必需知识点，或明确选择“无关联”。未勾选不能当成无关联。
3. 核查 `family_id`。同一原问题和改写同组；拆分可用 `dev-family-001-a` 等新编号，合并则统一编号。两人使用不同编号也会产生待裁决分歧。
4. 填写判定理由、家族调整说明，勾选已核查，点击“确认本题”。修改标签、家族、理由或复核人后，需要重新确认。
5. 定期“导出复核记录”。浏览器暂存不能替代导出备份；更换设备可用“恢复已导出记录”。允许导出未完成进度，但汇总会拒绝未确认条目。

负责人将回收文件保存为 `a.jsonl`、`b.jsonl` 后执行：

```powershell
.\.venv\Scripts\python.exe -m course_matcher.review compare `
  --packet data/annotations/review-nlp-v1 `
  --a data/annotations/review-nlp-v1/a.jsonl `
  --b data/annotations/review-nlp-v1/b.jsonl `
  --output data/annotations/review-nlp-v1/comparison
```

`comparison.json` 分别统计标签一致条数、家族一致条数，并保留两人的原始判断和理由。它们是直接一致数，不是模型准确率，也不是校正偶然一致性的系数。标签或家族不一致时会生成 `adjudication.html`，由不同于 A、B 的第三人填写、确认并导出裁决记录。

```powershell
.\.venv\Scripts\python.exe -m course_matcher.review finalize `
  --packet data/annotations/review-nlp-v1 `
  --a data/annotations/review-nlp-v1/a.jsonl `
  --b data/annotations/review-nlp-v1/b.jsonl `
  --adjudication data/annotations/review-nlp-v1/adjudication.jsonl `
  --dataset-version reviewed-development-nlp-v1 `
  --output data/annotations/reviewed-development-nlp-v1
```

没有分歧时省略 `--adjudication`。输出的 `questions.jsonl` 保留原始问题来源、两份复核及裁决记录；`nodes.json` 保留原文快照；`dataset.json` 记录版本和用途。缺题、重号、正文被改动、未知节点、未签核、空理由、A/B 同人和未解决分歧会使命令失败。

工具检查填写完整性，不能核实人员身份或代替教学判断。开发题经复核后标签可为 `confirmed`，其数据用途仍为 `development`，原来的手写来源也会保留；不能据此宣称已有独立真实课堂测试。

## 真实课堂独立评价集

正式课堂评价采用未参与开发的真实课堂提问。先由提供者脱敏并确认用途，再按同样的 A/B 流程标注。现有数据库中的模型匹配记录和浏览器验收批次没有足够的真实课堂来源证明，不自动纳入。

用户另要求先生成几个问题，因此补充了 `data/annotations/ai-supplement-nlp-v1.jsonl`：16 条 `source=ai-authored`、`label_status=pending_review` 的问题，不预填知识点标签。它们覆盖单知识点、组合问题、图谱边界和课程事务等候选情形，实际标签由复核人判断。生成时已接触现有开发题，因此这些候选只能作为补充开发材料，不能冒充未见课堂题；是否与开发题同源仍须人工核查。

```powershell
.\.venv\Scripts\python.exe -m course_matcher.review prepare `
  --input data/annotations/ai-supplement-nlp-v1.jsonl `
  --nodes data/annotations/curriculum-nodes-v1.json `
  --dataset-version ai-supplement-nlp-v1 `
  --output data/annotations/review-ai-supplement-nlp-v1
```

`training/templates/classroom-question.json` 是一条问题的空白结构，不是实际样本。将每条完整对象压成一行，组成 UTF-8 JSONL，保存在忽略目录，例如 `data/annotations/classroom-heldout-v1/raw.jsonl`。字段要求如下：

| 字段 | 填写要求 |
| --- | --- |
| `id` | 稳定、唯一、脱敏后的问题编号 |
| `family_id` | 人工核查的同源家族编号，同一原问题的改写保持一致 |
| `question` | 脱敏后的原始课堂表述，不为匹配节点而改写 |
| `source.course_id` | 与冻结图谱相同的课程；当前为 `nlp-curriculum` |
| `source.session` | 实际课次或日期，便于追溯 |
| `source.record_id` | 不含学生身份的来源记录编号 |
| `source.deidentified` | 提供者确认脱敏后填写 `true` |
| `source.used_in_development` | 确认未用于开发、试验或调参后填写 `false`；不确定时不能纳入 |

先固定完整的已用开发数据清单，再生成课堂复核包。`--exclude` 可以重复指定，应覆盖实际使用过的开发问题；下例为当前开发集：

```powershell
.\.venv\Scripts\python.exe -m course_matcher.review prepare `
  --origin classroom `
  --input data/annotations/classroom-heldout-v1/raw.jsonl `
  --exclude data/annotations/development-nlp-v1.jsonl `
  --nodes data/annotations/curriculum-nodes-v1.json `
  --dataset-version classroom-heldout-v1 `
  --output data/annotations/review-classroom-heldout-v1
```

工具检查来源字段、课程、脱敏与开发使用声明，以及问题 ID、家族和规范化文本是否与已用开发数据重叠。规范化仅处理大小写、全半角、空白和标点，无法识别语义改写；是否同源、是否真正未参与开发仍需人工确认。匹配错误或更好的测试分数不能作为删除问题、修改金标准或调整阈值的理由。

用课堂复核包执行 `compare`、`finalize` 后，输出记录带有 `split_role=heldout`，用途为 `independent_evaluation_only`。训练划分会拒绝这类记录。先冻结模型、候选预算和验证集阈值，再对这份保留集做一次独立评价；不要交给现有随机划分命令重新切分。目前尚无已确认来源的真实课堂原始题，正式评价需等待提供者交付及人工复核。
