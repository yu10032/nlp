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
    fontSize: "12.5px"
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

工作台围绕教师整理课程讲义、核对证据和签核教学内容的真实场景展开：米白纸面承托暖白讲义页，内容以宋体排版，操作与注记以黑体呈现。机器预测、教师确认、审核签章与原文定位分别对应铅笔、墨笔、朱批与荧光四类笔迹语义。

**Key Characteristics:**
- 温暖纸底与轻柔讲义纸页，减少冗余边框嵌套。
- 宋体承载问题、答复、引文与图谱词条；黑体承载导航、控件与注记。
- 左讲义页、右页边旁注栏并列，核查原文不中断当前编辑状态。

## Colors

### Paper & Ink

`paper`（`#f5f1e8`）作为全局背景，`sheet`（`#fffdf8`）作为讲义工作面；浓墨 `ink`（`#1f1c17`）承担正文、主要操作与当前选中节点，铅笔灰 `pencil`（`#9a9283`）表达候选与归档。

### Semantic Pens

- **钢笔蓝（`#284a7e`）**：只用于链接、可点击动作与键盘焦点。
- **朱批（`#b4412c`）**：只用于教师审核（审核通过、方印「审」、审核失效与覆盖缺口）。
- **荧光（`#f3dc7a`）**：只用于原文定位与当前引用句子标记。

**The Pen Separation Rule.** 三支笔的语义互不混用：看到红色即涉及审核或缺口，看到荧光即指向课程原文依据。

## Typography

内容文本采用中文衬线字体栈（思源宋体优先），正文 `16px / 1.9`；界面控制与注记采用中文无衬线字体栈，全局启用等宽数字（`tabular-nums`）。关系谓词与词条别名采用斜体排印。

## Layout

顶部采用 `56px` 纸色粘性顶栏，整合品牌、课程切换、流程分组导航（资料·图谱 | 提问·答疑·出题·备课 | 覆盖·实验）与真实服务状态。窄屏（`980px` 以下）折叠导航菜单并按任务顺序纵向排列讲义页与旁注栏；图谱工具栏与图例固定于画布外侧底部，避免遮挡节点。

## Components

### Buttons & Disabled State

主操作采用浓墨实底，次要操作采用讲义白底细框，审核通过采用朱色描边按钮。禁用按钮统一采用铅笔虚线边框并在相邻位置说明不可用原因。

### Status Marks

- **机器预测 / 待确认**：铅笔色虚线下划线（可附预测得分）。
- **教师确认**：浓墨实线下划线配勾选符号。
- **审核通过**：朱色双框方印「审」与版本签核注记。
- **审核失效**：朱色删除线。

### Margin Notes & Source Reader

答疑页右侧以编号旁注列出课程依据，已引用条目浮起为暖白纸签；点击「查看原文」在同一侧栏展开整篇资料并用荧光标出目标段落，返回后保留未保存正文与引用勾选。
