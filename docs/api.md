# 接口约定

统一前缀 `/api/v1`。完整字段、枚举和长度限制以运行中的 [OpenAPI](http://127.0.0.1:8000/docs) 和路由 schema 为准；前端调用集中在 `frontend/src/api.ts`。

成功直接返回对象；失败为 `{"error":{"code":"...","message":"..."}}`。ID 为 UUID 或既有演示 ID，时间使用 UTC ISO 8601。所有课程资源限定路径中的课程；越界返回 404，版本冲突或模型范围不符返回 409，业务输入不符返回 422。当前没有用户身份鉴权。

## 接口入口

以下路径除 `/health`、`/courses` 外，均位于 `/courses/{course_id}` 下。

| 接口 | 用途 |
| --- | --- |
| `GET /health`；`GET/POST /courses` | 状态、课程列表与创建 |
| `GET/POST /documents`；`GET /jobs/{id}` | 资料列表与上传、解析状态；换版使用 `?replaces_id=旧版本ID` |
| `GET /documents/{id}/chunks`、`/file`、`/images/{relation}` | 段落、原件、同课程 DOCX 插图 |
| `GET /graph`；`POST /nodes`；`GET/PATCH /nodes/{id}` | 图谱及有来源的节点维护 |
| `POST /edges`、`/edges/{id}/review` | 关系创建与确认／驳回，先修关系禁止环 |
| `POST /matches`、`/matches/compare`；`GET /matcher`、`/experiments` | 不持久化的节点匹配、方法可用性与实验产物 |
| `GET /questions`、`/questions/{id}`；`POST /questions/match`、`/questions/batch` | 最近 100 条问题、详情、持久化匹配和每批 1–50 条导入 |
| `POST /questions/{id}/links`；`GET /nodes/{id}/questions` | 确认零至多个节点；从全部历史反查，返回总数及最近 50 条 |
| `GET/POST /question-batches`；`GET /question-batches/{id}` | 最近 50 批、导入及批次全部原问题和相似组 |
| `POST /question-batches/{id}/groups`；`PATCH/DELETE /question-groups/{id}`；`POST /question-groups/merge` | 人工建组、成员修订／解散、组间合并 |
| `POST /evidence/retrieve`；`GET/POST /evidence/comparisons` | 检索、保存对照及最近 50 条历史 |
| `GET /evidence/comparisons/{id}`、`/{id}/export`；`PATCH /evidence/comparisons/{id}/assessment` | 对照快照、JSON 导出与人工评价 |
| `GET/POST /drafts`；`GET/PATCH /drafts/{id}`；`POST /drafts/{id}/review`；`GET /drafts/{id}/export` | 答疑草稿、修订、审核与 Markdown 导出 |
| `GET/POST /teaching/{kind}`；`GET/PATCH /teaching/{kind}/{id}`；`POST .../{id}/review`；`GET .../{id}/export` | `kind=quiz/lesson`，题组和讲义的同类生命周期 |
| `GET /coverage` | 有效资料、已审核题组和讲义覆盖 |

## 版本、匹配与审核

- `Material.id` 为具体资料版本，`document_id` 为同一资料；新版本成功后替换旧版。旧原文仍可读取，DOCX 不捏造页码。
- `/matches` 输入 `question/method`，默认 `name`；`method` 保留旧响应的版本语义，另含 `method_id/version`。`/questions/match` 输入 `question_text/method/max_suggestions`，默认 `auto`，支持 `name/tfidf/embedding/mlp`，保存真实 `model_version/graph_version`。不可用模型不伪装为其他方法。
- 问题结果保留 `predictions/confirmed_node_ids/needs_review`，确认不覆盖预测。节点反查区分 `confirmed/predicted/not_selected`。
- 新批次输入 `title/questions`，每批 1–50 条，逐问匹配字段沿用原接口。返回 `questions/groups/grouping_version/similarity_threshold`；兼容 `/questions/batch` 仍返回问题数组，但也保存批次。问题增加可空的 `batch_id/group_id`，旧记录保留；`GET /questions?batch_id=...` 可按批次筛选。
- 建组／修订使用 `question_ids/title`，至少两个不同问题；修订和解散要求 `expected_version`。成员须同课程、同批次且无其他组归属，移入其他组需先移出或合并。修订默认确认，`confirm=false` 保持候选；合并使用 `group_ids/expected_versions` 并回到待确认。分组操作返回更新后的批次，不改变预测、知识点标签或训练家族。
- 教学编辑和审核携带 `expected_version`。草稿允许不完整；审核／导出检查当前版本、具体项知识点、有效引用及题组依赖。修改后旧审核失效，失效内容退出正式覆盖。

## 教学与分段生成

题组／讲义创建使用 `title/target_node_ids/body/generate`，目标为 1–5 个已确认具体节点。题组最多 5 题，逐题保存题干、选项、答案、解析、知识点和引用；单选答案 A–D。

新讲义采用 `format_version=2`，含目标、准备、课后任务和最多 24 个环节。环节有稳定 `id`、类型、分钟数、讲解、师生互动、反馈及引用；总时长须一致。审核要求四类环节、例题与易错点，正文至少 `duration * 60` 个非空白字符，每段至少 `min(120, minutes * 15)`；篇幅检查不代表教学质量。

以下路径位于 `/teaching/lesson/{id}` 下：

| 方法与后缀 | 约定 |
| --- | --- |
| `POST /confirm-plan` | `expected_version`；确认安排，不调用模型 |
| `POST /segments/{segment_id}/generate` | `expected_version`、可选 `rewrite_instruction`；只替换当前段并保存修订 |
| `GET /word?audience=teacher` | 下载已审核 DOCX；`teacher/student`，默认教师版 |
| `GET /print?expected_version=N&audience=teacher` | 打印前重查版本、审核、引用及例题，返回当前版本 |

调整目标、环节安排或题组分配会使安排确认失效；正文编辑仍使内容审核失效。分段生成检查安排与引用不变、正文至少 `minutes * 60`，超时 180 秒；答疑／出题超时 60 秒，不自动重试。生成返回后重查版本，失败不保存当前段。

学生版使用结构化的无答案题目和 `student_homework`，隐藏独立教师字段；讲解中的示范推导保留。旧题组快照缺少学生内容时，重新保存并审核后导出。旧提纲和旧资料不自动改写或重解析。

## 检索对照

检索输入 `question_text/node_ids/mode/evidence_budget`，`mode=basic/graph_augmented`，预算为 1–10 段。返回原文版本、`node_evidence` 和是否缺少依据；增强证据含 `graph_paths`，记录关系方向、边版本和来源。

创建对照共用问题、资料与条数预算，可绑定文本一致的 `question_id`；目标必须同课程且已确认。`snapshot` 保存目标、图谱／资料版本、两组完整证据与 `difference.shared/added/removed`。`is_stale` 提示课程变化，保留原快照；对照本身不调用生成 API。

评价使用 `reviewer/relevance/outcome/note`。`relevance` 只接受本次片段 ID，值为 `relevant/irrelevant/uncertain`；`outcome=better/worse/mixed/same/uncertain`。评价独立于教学审核和覆盖，补入条数不能作为质量指标。
