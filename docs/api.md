# 接口约定

统一前缀 `/api/v1`；实际 schema 见 `/docs` 和 `/openapi.json`。成功响应直接返回对象；失败为 `{"error":{"code":"...","message":"..."}}`。
ID 为 UUID 或已有演示 ID；时间使用 UTC ISO 8601；所有课程资源均受路径中的 `course_id` 约束。

| 方法 | 相对路径 | 行为 |
| --- | --- | --- |
| GET | `/health` | 进程状态、生成配置是否齐全、实际匹配方式；不发外部探测请求 |
| GET / POST | `/courses` | 列表与创建课程 |
| GET / POST | `/courses/{c}/documents` | 资料版本列表；单文件上传，返回 `job_id/material_id/status` |
| GET | `/courses/{c}/jobs/{job}` | 持久化解析状态与错误 |
| GET | `/courses/{c}/documents/{version_id}/chunks` | 当前或历史版本的原文与位置 |
| GET | `/courses/{c}/documents/{version_id}/file` | 下载原文件 |
| GET | `/courses/{c}/graph` | `version/nodes/edges` |
| POST | `/courses/{c}/nodes` | 创建有来源的候选或人工确认节点 |
| GET / PATCH | `/courses/{c}/nodes/{node}` | 详情及来源；保存完整编辑表单 |
| POST | `/courses/{c}/edges` | 创建有来源的候选关系 |
| POST | `/courses/{c}/edges/{edge}/review` | `confirmed/rejected`，确认先修时检查有向环 |
| POST | `/courses/{c}/matches` | 原名称/别名基线，不持久化问题 |
| GET | `/courses/{c}/questions` | 最近 100 个问题及预测、确认关联 |
| GET | `/courses/{c}/questions/{q}` | 单问题历史 |
| POST | `/courses/{c}/questions/match` | 保存新问题、图谱版本、方法和原始预测 |
| POST | `/courses/{c}/questions/{q}/links` | 人工确认零至多个节点，保留机器预测 |
| POST | `/courses/{c}/evidence/retrieve` | 同课程原文检索和可选的一跳补充 |
| GET / POST | `/courses/{c}/drafts` | 答疑列表；创建手工/在线草稿 |
| GET / PATCH | `/courses/{c}/drafts/{d}` | 正文、引用、历史修订、审核记录；编辑增加版本 |
| POST | `/courses/{c}/drafts/{d}/review` | 按当前版本审核，通过或退回 |
| GET | `/courses/{c}/drafts/{d}/export` | 仅导出当前有效审核版本，含课程依据 |
| GET | `/courses/{c}/coverage` | 三项同分母覆盖，不统计章节和失效审核 |

## 核心字段

- `Material.id` 是具体版本 ID，`document_id` 把同一资料的各版本归为一组。上传新版本使用 `?replaces_id=<旧版本 ID>`，只有新版本解析成功才停用旧版本。
- 资料状态：`ingesting/ready/partial/failed`；解析任务：`queued/running/done/failed`。重启中断的解析标记失败，用户重新上传；不伪装为可自动恢复的任务队列。
- `Chunk` 保存 `material_id/text/section_path/locator/page_from/page_to/paragraph_locator/position`。DOCX 不捏造页码；不可读图像和公式进入解析提示。
- 节点编辑使用 `name/aliases/description/kind/status/evidence_chunk_ids`。确认节点必须有有效同课程片段。
- 问题匹配输入 `question_text/method/max_suggestions`；方法为 `name` 或 `tfidf`，返回 `id/text/model_version/graph_version/predictions/confirmed_node_ids/needs_review`。当前 TF-IDF 阈值 0.1 是开发参数，尚未经过正式验证集选择。
- 检索输入 `question_text/node_ids/mode/evidence_budget`；`mode=basic/graph_augmented`。返回原文、资料版本和来源，`missing_evidence=true` 不调用生成器。
- 草稿输入 `question_id/title/answer/node_ids/citation_ids/generate/retrieval_mode`。`generate=true` 使用后端取得的证据，校验输出引用归属，不接受前端伪造的原文。
- 修改草稿与审核均携带 `expected_version`。版本冲突返回 409；每次编辑保存修订快照。审核记录含版本、结果、审核人和时间。
- 教学内容状态：`draft/approved/rejected/stale_review`。仅当前 `approved` 且依赖有效时可导出。第一阶段未增加没有操作语义的中间“提交审核”步骤。

当前审核人是本地操作人填写的名称；登录身份与课程成员权限仍待后续接入，不能把课程范围查询当作已完成用户鉴权。
题库、备课与批量提问接口已实现；语义分组与正式模型评测尚未接入。

## 出题与备课

统一路径 `/courses/{c}/teaching/{kind}`，`kind=quiz/lesson`。

| 方法 | 路径后缀 | 行为 |
| --- | --- | --- |
| GET / POST | 空 | 最近 100 份列表；创建手工或生成草稿 |
| GET / PATCH | `/{id}` | 读取完整内容；保存完整表单并提升版本 |
| POST | `/{id}/review` | 当前版本教师审核，通过前检查内容与依赖 |
| GET | `/{id}/export` | 仅导出有效审核版本，Markdown 含正文和课程依据 |

创建输入 `title/target_node_ids/body/generate`，目标 1–5 个已确认的具体知识点；更新改用 `expected_version`，不接受生成开关。生成始终建立新草稿，不覆盖当前版本。响应在原草稿字段上增加 `kind/body`，修订快照也保留结构化正文。

- 题组 body：`difficulty=basic/intermediate/advanced`，`items` 为 1–5 题，`missing_info` 为待补充事项。逐题字段：`type=single_choice/short_answer`、`stem/options/answer/explanation/node_ids/citation_ids`。单选四项，答案 A–D；简答的 options 为空。草稿可留白，生成输出与通过审核时检查完整性、答案选项一致性和组内近重复题干。
- 备课 body：`duration/objectives/key_questions/segments/missing_info`；duration 为 5–240 分钟。逐段字段：`title/minutes/content/activity/example/node_ids/citation_ids/quiz_ids`，最多 12 段。quiz_ids 指向同课程已审核题组；保存时记录 examples 快照。审核、导出时重新确认例题版本仍有效。分段总时长必须等于 duration 才能审核。
- 教学节点和引用按具体题目/环节聚合后保存，不能通过仅选择生成目标增加覆盖。审核还要求所有目标都已关联到具体内容。
- 题组编辑或退回会使引用它的已审核备课失效；资料替换使所有受影响的已审核内容失效。原答疑 PATCH 不能改写题组或教案。

## 批量提问

`POST /courses/{c}/questions/batch` 输入 `questions: [{question_text, method?, max_suggestions?}]`，一次 1–50 条，返回问题结果数组，整批一次提交。单条约束与 `/questions/match` 相同；原始预测保留，人工关联仍通过 `/questions/{id}/links` 修改。

前端热点基于 `/questions` 的最近 100 条，已确认关联频次与待确认预测频次分别计算；不把未匹配条目删掉，不将此频次称作全课程累计或语义分组。
