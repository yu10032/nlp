---
name: 课程智能助教
description: 讲义与批注——以课程依据为中心的教学工作台
colors:
  paper: "#f5f1e8"
  sheet: "#fffdf8"
  sheet-warm: "#fcf9f2"
  rule: "#e4dccb"
  rule-strong: "#cbbfa6"
  ink: "#1f1c17"
  ink-2: "#47423a"
  ink-3: "#6e675b"
  pencil: "#9a9283"
  indigo: "#284a7e"
  zhu: "#b4412c"
  mark: "#f3dc7a"
  ochre: "#85500f"
typography:
  headline:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Songti SC, STSong, Georgia, serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.22
    letterSpacing: "0.02em"
  entry-title:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Songti SC, STSong, Georgia, serif"
    fontSize: "32px"
    fontWeight: 600
    lineHeight: 1.22
  title:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Songti SC, STSong, Georgia, serif"
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.38
  body:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Songti SC, STSong, Georgia, serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.9
  control:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  label:
    fontFamily: "Noto Sans SC, Source Han Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "13px"
    fontWeight: 500
rounded:
  sheet: "2px"
  control: "4px"
spacing:
  tight: "8px"
  group: "16px"
  section: "28px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 16px"
  button-review:
    backgroundColor: "{colors.sheet}"
    borderColor: "{colors.zhu}"
    textColor: "{colors.zhu}"
    rounded: "{rounded.control}"
    padding: "0 16px"
  work-surface:
    backgroundColor: "{colors.sheet}"
    rounded: "{rounded.sheet}"
---

# Design System: 课程智能助教

## Overview

**Creative North Star: "讲义与批注"**

工作台围绕教师整理课程讲义、核对证据和签核教学内容的真实场景展开：米白纸面承托暖白讲义页，内容以宋体排版，操作与注记以黑体呈现。纸墨不是装饰主题，而是服务于三条任务秩序：下一步操作清楚、课程依据清楚、教师审核状态清楚。

**Design Principles:**

1. 内容优先：讲义、问题、答复与原文是主角，减少解释产品自身的文案。
2. 证据可达：生成内容可以在同页回到课程原文，核查不丢失编辑状态。
3. 人机有别：机器建议、教师确认与审核签核采用不同且稳定的视觉语义。
4. 状态明确：草稿、未保存、待审核、已审核与审核失效同时通过文字或形状表达，不只依赖颜色。
5. 每屏一个主动作：主按钮只用于当前工作区最关键的推进动作。
6. 按需说明：默认只呈现内容、状态与操作；模型版本、分数、参数和规则收进有明确名称的详情，不能用成片小字承担界面设计。

**Key Characteristics:**

- 温暖纸底与轻柔讲义纸页，以留白和细线分区，避免卡片嵌套。
- 宋体承载问题、答复、引文与图谱词条；黑体承载导航、控件与注记。
- 左讲义页、右页边旁注栏并列，核查原文不中断当前编辑状态。
- 不使用渐变、胶囊标签、装饰性指标卡和与任务无关的图标。

## Colors

### Paper & Ink

`paper`（`#f5f1e8`）作为全局背景，`sheet`（`#fffdf8`）作为讲义工作面；浓墨 `ink`（`#1f1c17`）承担正文、主要操作与当前选中节点，铅笔灰 `pencil`（`#9a9283`）只承担候选、占位与非关键装饰，不用于必须阅读的小字。

### Semantic Pens & System States

- **钢笔蓝（`#284a7e`）**：只用于链接、可点击动作与键盘焦点。
- **朱批（`#b4412c`）**：只用于教师审核、退回、审核失效与覆盖缺口。
- **荧光（`#f3dc7a`）**：只用于原文定位与当前引用句子标记。
- **赭石（`#85500f`）**：用于系统警告与操作错误，不借用审核朱红。
- **状态绿（`#4f7a52`）**：只用于服务可用和保存成功。

**The Pen Separation Rule.** 三支笔的语义互不混用：看到红色即涉及审核或缺口，看到荧光即指向课程原文依据。系统状态同时提供文字或图标，不能仅靠颜色传达。

## Typography

内容文本采用中文衬线字体栈（思源宋体优先），正文 `16px / 1.85–1.9`；界面控制与注记采用中文无衬线字体栈，全局启用等宽数字（`tabular-nums`）。关系谓词与词条别名采用斜体排印。

- 页面标题：`28–30px / 1.25`，字重 600。
- 区段标题：`18px / 1.4`，字重 600。
- 教学正文：`16px / 1.85`。
- 控件正文：`14px / 1.5`。
- 控件标签与操作说明采用 `14px`；来源位置、历史时间等低频元信息可用 `13px`。层级由位置、间距与字重建立，不持续缩小字号。

## Spacing & Shape

采用 `4px` 基础网格，常用间距为 `8 / 12 / 16 / 24 / 32 / 48px`。讲义页圆角 `2px`，控件圆角 `4px`。阴影只用于浮动讲义、原文阅读层与下拉菜单；分区优先使用留白与细线。

## Layout

顶部采用 `56px` 纸色粘性顶栏，整合品牌、课程切换与流程分组导航（资料·图谱 | 提问·答疑·出题·备课 | 覆盖·实验）。桌面端生成服务和匹配器合并为一个「系统状态」入口，点击后查看真实状态；窄屏在导航菜单中直接展示状态。

页面标题区左侧放置页面名称和当前状态，右侧只放历史、新建等页面级操作。主内容最大宽度为 `1360px`。保存与审核集中在工作面底部，生成与检索留在对应编辑区，不与最终签核混排。

桌面端讲义与依据采用双栏；`1024px` 以下改为单栏。答疑页窄屏顺序为教学问题、关联知识点、课程依据、答复、审核，避免编辑答复时长距离回滚核查。移动端主要控件点击区域为 `40–44px`。图谱工具栏与图例固定于画布外侧底部，避免遮挡节点。

## Components

### Buttons & Disabled State

主操作采用浓墨实底，次要操作采用讲义白底细框，轻量动作采用文字按钮，审核通过采用朱色描边按钮。每个工作区最多一个主按钮。禁用按钮统一采用铅笔虚线边框，并在相邻位置动态说明缺少的条件，不让用户通过反复点击猜测原因。

### Section Order

答疑页默认突出问题、答复和课程依据，不添加装饰性步骤编号。检索参数按需展开；知识点待确认时展开，确认后以名称概括。保存与审核集中在底部，当前版本状态只在页头表达一次。

### Status Marks

- **机器预测 / 待确认**：铅笔色虚线下划线（可附预测得分）。
- **教师确认**：浓墨实线下划线配勾选符号。
- **审核通过**：朱色双框方印「审」与版本签核注记。
- **审核失效**：朱色删除线。
- 当前版本状态集中表达，避免在标题、正文和底部无意义重复。

### Margin Notes & Source Reader

答疑页右侧以编号旁注列出课程依据，桌面端保持可见。每条依据提供编号、来源、位置、引文与操作；长引文默认显示四行，可单独展开。已引用条目以明确的勾选和文字表达，不叠加浮动卡片。章节路径和版本可从原文核查，点击「查看原文」在同一侧栏展开资料，返回后保留未保存正文与引用勾选。

### Motion & Accessibility

交互反馈使用 `120–180ms` 的轻量过渡，并尊重减少动态效果偏好。所有功能保留键盘焦点与可读标签；状态不只靠颜色，正文和辅助文字保持足够对比度。

### 教学讲义与提问核查

出题与备课共用左侧讲义、右侧依据旁注的工作面。题目以题干、选项、答案、解析顺序编辑；教案以分钟数、讲解、课堂活动、例子顺序编辑。每题和每段都直接列出知识点与引用编号，原文在同页展开。顶部选择教学范围，底部保存与朱批审核，不添加装饰性指标卡。

提问页以原始记录和关联核查并列，热点按节点展示已确认与待确认数量。窄屏顺序为导入、热点、原始记录、核查，保留实际来源与人工确认语义。

### 本地模型实验

同输入对照与指标台账默认可见，训练记录、复现参数、指标说明和错误案例按需展开。训练损失用墨色实线、验证损失用钢笔蓝虚线；错误案例保留参考标签与模型关联。开发数据状态始终明确显示，不用装饰性指标卡或“训练成功”替代效果信息。

### 图谱问题核查与证据对照

图谱上方直接录入教学问题，原始建议采用铅笔虚线，保存后的人工确认采用墨色实线；节点旁栏反查原提问。实验页以两个并列讲义面展示证据，正文、来源、补入路径和相关性依次排布。共同片段共享评价，原文在同页展开；窄屏按普通组、增强组、人工核查顺序排列。不用差异数量表达质量提升，不用审核朱色装饰实验状态。
