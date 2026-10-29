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

创建输入 `title/target_node_ids/body/generate`，目标 1–5 个已确认的具体知识点；更新改用 `expected_version`，不接受生成开关。原创建接口的 `generate=true` 始终建立新草稿；课堂讲义页面现采用下述分段接口，在已有草稿上逐段创建修订。响应在原草稿字段上增加 `kind/body`，修订快照也保留结构化正文。

- 题组 body：`difficulty=basic/intermediate/advanced`，`items` 为 1–5 题，`missing_info` 为待补充事项。逐题字段：`type=single_choice/short_answer`、`stem/options/answer/explanation/node_ids/citation_ids`。单选四项，答案 A–D；简答的 options 为空。草稿可留白，生成输出与通过审核时检查完整性、答案选项一致性和组内近重复题干。
- 课堂讲义 body：`format_version/plan_confirmed/duration/objectives/key_questions/preparation/homework/student_homework/segments/missing_info`；duration 为 5–240 分钟，最多 24 段。student_homework 单独保存不含答案的学生版课后任务；旧版混合的 homework 不自动发给学生。新建页面和自动生成采用 `format_version=2`；旧内容未带此字段时按 `1` 读取，保留原提纲的编辑和审核规则，不批量改写历史数据。missing_info 最多 500 项，合并分段生成的待补充事项，不静默截断。
- 逐段字段：`id/title/minutes/content/activity/example/node_ids/citation_ids/quiz_ids`，以及 `stage=opening/instruction/practice/summary`、`student_activity/expected_response/check_for_understanding/misconceptions`。id 为稳定的环节标识，排序后仍对应同一环节；旧稿保存时补齐。content 上限 16000 字符；其余上限见 OpenAPI。quiz_ids 指向同课程已审核题组，保存时记录 examples 快照，审核和导出时重查版本；活动和互动时间包含在 minutes 内，各段之和须等于 duration。
- 完整讲义审核和生成校验：须含课前准备、课后巩固、导入/讲解/练习/总结四类环节，首段导入、末段总结；每段有教师引导、学生任务、参考回答、检查反馈，全课至少一份例题演示及易错点。讲解正文非空白字符合计至少 `duration * 60`（45 分钟为 2700 字符），每段至少 `min(120, minutes * 15)`，用于拦截简略提纲，并不代表事实正确或教学质量合格。草稿仍可不完整保存。
- 自动生成始终要求 v2，不接受降级的旧提纲；提示词要求展开概念、推导（适用时）、完整例题、具体互动步骤、练习和答案、总结检测，事实依赖本次课程依据，证据缺口写入 missing_info。单次请求的输出预算为 `min(32000, max(8000, duration * 320))` tokens，HTTP 超时为 180 秒；截断、过短或缺项均报错且不保存，不自动重试。答疑和出题仍使用原有 60 秒超时，不额外指定输出预算。

新增字段存于既有 TeachingContent/ContentRevision 的 JSON 正文，不新增数据库列，无需迁移。当前 `lesson-v2` 仅完成离线模拟验证，尚未使用真实模型服务验收长篇生成效果。

### 分环节生成、预览与成品导出

| 方法 | `/courses/{c}/teaching/lesson` 后缀 | 行为 |
| --- | --- | --- |
| POST | `/{id}/confirm-plan` | 输入 expected_version，检查目标、四类环节、顺序、时长、标题与知识点分配，保存确认修订；不调用模型 |
| POST | `/{id}/segments/{segment_id}/generate` | 输入 expected_version、可选 rewrite_instruction（最多 2000 字符）；只生成或重写指定环节并保存新版本 |
| GET | `/{id}/print?expected_version=N&audience=teacher` | 打印前重新核查当前审核、引用、关联题组和版本；audience=teacher/student，成功返回 version |
| GET | `/{id}/word?audience=teacher` | 下载当前有效审核讲义的 DOCX；audience=teacher/student，默认教师版 |

plan_confirmed 由确认接口控制，客户端无法在普通保存时直接置为 true；调整课时、目标、重点问题、环节顺序/标识/标题/类型/用时/知识点或题组分配后失效。只修改正文、互动、准备与作业保留安排确认，但原内容审核仍失效。

分段接口必须已有确认安排；仅使用该段目标的同课程有效依据、所选题组和前两段的有限衔接正文。输出须保持该段安排和关联不变，正文至少 minutes * 60 个非空白字符，包含具体互动与反馈；讲解和练习须有例题，导入须给课前准备，总结须给课后巩固。单次输出预算 `min(20000, max(4000, minutes * 320))`，超时 180 秒，不自动重试。生成前结束读取事务，生成后重新读取讲义版本；并行编辑返回 409，不覆盖新内容。失败段不保存，已完成段保持原版本。

前端顺序调用空白环节，跳过已有正文；停止按钮在当前请求完成后停止后续环节。局部重写为明确的替换操作，修订历史保留原内容。课前准备和课后巩固只有原字段为空时才采用生成值，不覆盖教师输入。分段待补充事项合并到正文，教师可手工核查并删除已解决项。

阅读预览支持 Markdown 和本地 KaTeX 公式，输入 HTML 转义，图片只加载同课程原文插图。正式 PDF 通过浏览器“打印 / 保存 PDF”输出，服务端不依赖浏览器或 Word；打印前重查审核版本。DOCX 通过 python-docx 与 LaTeX → MathML → Office Math 转换生成，公式可编辑；不支持的公式会明确报错，不降级为假公式或空结果。预览和 Word 的页数可因排版引擎不同而变化。

教师版包含全部教学字段，学生版只保留目标、重点问题、课堂安排、讲解正文、学生任务、无答案的题组题干/选项、student_homework 与课程依据。教师引导、单列的例题解析、预期回答、反馈、易错提示、混合 homework 和待补充事项隐藏。讲解正文中的示范推导保持原文，发放前仍需教师预览确认。题组快照新增 student_content，由已审核结构化题目生成，不从答案 Markdown 猜测或删除文本；旧快照没有此字段时学生版打印/导出返回 409，要求重新保存并审核。

### 原文公式、插图与按目标分配依据

新上传 DOCX 使用 paragraph-v3：保留段内、表格内的常见 Word 公式为 LaTeX（分式、上下标、根式、求和/积分、括号和矩阵等），无法完整提取的公式在原位置和解析警告中提示回看原件。插图使用 `![说明](asset:rIdN)` 保留原文关系引用，不进行图像内容识别。`GET /courses/{c}/documents/{material_id}/images/{rIdN}` 从该资料的原 DOCX 返回 PNG/JPEG/GIF/WebP，限制在同课程，其他格式明确要求下载原件。旧资料不自动重新解析；上传替换版本后才能取得新解析结果。

检索的 graph_augmented 模式先为每个目标分配一份有效直接依据，再以词面相关性补足 budget；新增 node_evidence：`[{node_id, citation_ids, has_active_source}]`。has_active_source 指该节点是否有有效直接原文，citation_ids 指本次选入的直接依据。分段生成发现任一目标缺少有效直接依据时返回 422，提示补充资料。

- 教学节点和引用按具体题目/环节聚合后保存，不能通过仅选择生成目标增加覆盖。审核还要求所有目标都已关联到具体内容。
- 题组编辑或退回会使引用它的已审核备课失效；资料替换使所有受影响的已审核内容失效。原答疑 PATCH 不能改写题组或教案。

## 批量提问

`POST /courses/{c}/questions/batch` 输入 `questions: [{question_text, method?, max_suggestions?}]`，一次 1–50 条，返回问题结果数组，整批一次提交。单条约束与 `/questions/match` 相同；原始预测保留，人工关联仍通过 `/questions/{id}/links` 修改。

前端热点基于 `/questions` 的最近 100 条，已确认关联频次与待确认预测频次分别计算；不把未匹配条目删掉，不将此频次称作全课程累计或语义分组。
