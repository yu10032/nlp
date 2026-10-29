"""两种教学内容的结构、审核条件与可读导出。草稿允许留白，签核检查完整性。"""

import re
from difflib import SequenceMatcher
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

TeachingKind = Literal["quiz", "lesson"]
LESSON_STAGES = {
    "opening": "导入与复习",
    "instruction": "讲解与示范",
    "practice": "练习与应用",
    "summary": "总结与检测",
}


def lesson_minimum_chars(duration: int) -> int:
    """展开程度的下限，不代表教学质量或逐字朗读速度。"""
    return duration * 60


class LinkedPart(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    node_ids: list[str] = Field(default_factory=list, max_length=5)
    citation_ids: list[str] = Field(default_factory=list, max_length=20)


class QuizItem(LinkedPart):
    type: Literal["single_choice", "short_answer"] = "short_answer"
    stem: str = Field(default="", max_length=3000)
    options: list[str] = Field(default_factory=list, max_length=4)
    answer: str = Field(default="", max_length=4000)
    explanation: str = Field(default="", max_length=5000)


class QuizBody(BaseModel):
    difficulty: Literal["basic", "intermediate", "advanced"] = "basic"
    items: list[QuizItem] = Field(min_length=1, max_length=5)
    missing_info: list[str] = Field(default_factory=list, max_length=20)


class LessonSegment(LinkedPart):
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=80)
    stage: Literal["opening", "instruction", "practice", "summary"] = "instruction"
    title: str = Field(default="", max_length=200)
    minutes: int = Field(default=5, ge=1, le=240)
    content: str = Field(default="", max_length=16000)
    activity: str = Field(default="", max_length=2000)
    example: str = Field(default="", max_length=3000)
    student_activity: str = Field(default="", max_length=3000)
    expected_response: str = Field(default="", max_length=4000)
    check_for_understanding: str = Field(default="", max_length=3000)
    misconceptions: str = Field(default="", max_length=3000)
    quiz_ids: list[str] = Field(default_factory=list, max_length=5)


class LessonBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    # 旧 JSON 无此字段，仍按提纲读取；新讲义及生成输出使用 v2。
    format_version: Literal[1, 2] = 1
    plan_confirmed: bool = False
    duration: int = Field(default=45, ge=5, le=240)
    objectives: str = Field(default="", max_length=3000)
    key_questions: str = Field(default="", max_length=3000)
    preparation: str = Field(default="", max_length=4000)
    homework: str = Field(default="", max_length=5000)
    student_homework: str = Field(default="", max_length=5000)
    segments: list[LessonSegment] = Field(min_length=1, max_length=24)
    missing_info: list[str] = Field(default_factory=list, max_length=500)


def lesson_plan(body: dict) -> dict:
    return {
        **{key: body[key] for key in ("duration", "objectives", "key_questions")},
        "segments": [
            {key: part[key] for key in ("id", "stage", "title", "minutes", "node_ids", "quiz_ids")}
            for part in body["segments"]
        ],
    }


def lesson_plan_issues(body: dict, target_ids: list[str]) -> list[str]:
    issues = []
    segments = body["segments"]
    if not body["objectives"].strip():
        issues.append("请填写教学目标")
    if sum(part["minutes"] for part in segments) != body["duration"]:
        issues.append("课堂安排的总时长需等于课时")
    if {part["stage"] for part in segments} != set(LESSON_STAGES):
        issues.append("课堂安排需包含导入、讲解、练习和总结检测")
    if segments[0]["stage"] != "opening" or segments[-1]["stage"] != "summary":
        issues.append("请将导入放在首段、总结检测放在末段")
    if any(not part["title"].strip() or not part["node_ids"] for part in segments):
        issues.append("每个环节需有标题并关联知识点")
    if set(linked_ids("lesson", body, "node_ids")) != set(target_ids):
        issues.append("课堂安排尚未覆盖全部目标知识点")
    if len({part["id"] for part in segments}) != len(segments):
        issues.append("环节标识重复，请重新添加重复的环节")
    return issues


def segment_issues(part: dict, index: int) -> list[str]:
    issues = []
    for key, label in [
        ("activity", "教师引导与活动步骤"),
        ("student_activity", "学生任务"),
        ("expected_response", "预期回答或参考答案"),
        ("check_for_understanding", "检查与反馈"),
    ]:
        if not part.get(key, "").strip():
            issues.append(f"第 {index} 段需填写{label}")
    if len(re.sub(r"\s", "", part["content"])) < min(120, part["minutes"] * 15):
        issues.append(f"第 {index} 段讲解需展开，不能只列标题或教学动作")
    return issues


def parts(kind: str, body: dict) -> list[dict]:
    return body["items" if kind == "quiz" else "segments"]


def linked_ids(kind: str, body: dict, key: str) -> list[str]:
    return list(dict.fromkeys(value for part in parts(kind, body) for value in part[key]))


def invalidate_lesson_examples(session, quiz_id: str, course_id: str):
    from sqlalchemy import select

    from ta_backend.models import TeachingContent

    for lesson in session.scalars(
        select(TeachingContent).where(
            TeachingContent.kind == "lesson",
            TeachingContent.status == "approved",
            TeachingContent.course_id == course_id,
        )
    ):
        if any(quiz_id in part["quiz_ids"] for part in lesson.body.get("segments", [])):
            lesson.status = "stale_review"
            lesson.reviewed_version = None


def completeness_issues(kind: str, body: dict) -> list[str]:
    issues = []
    if kind == "lesson":
        if not body["objectives"].strip():
            issues.append("请填写教学目标")
        total = sum(segment["minutes"] for segment in body["segments"])
        if total != body["duration"]:
            issues.append(f"分段共 {total} 分钟，与课时 {body['duration']} 分钟不一致")
        if body.get("format_version", 1) == 2:
            issues.extend(full_lesson_issues(body))
    stems = []
    for index, part in enumerate(parts(kind, body), 1):
        label = f"第 {index} {'题' if kind == 'quiz' else '段'}"
        if not part["node_ids"] or not part["citation_ids"]:
            issues.append(f"{label}需关联知识点和课程依据")
        if kind == "quiz":
            if any(not part[key].strip() for key in ("stem", "answer", "explanation")):
                issues.append(f"{label}需填写题干、答案和解析")
            if part["type"] == "single_choice":
                options = [option.strip() for option in part["options"]]
                if len(options) != 4 or any(not option for option in options):
                    issues.append(f"{label}需填写四个选项")
                elif len(set(options)) != 4:
                    issues.append(f"{label}存在重复选项")
                if part["answer"] not in ("A", "B", "C", "D"):
                    issues.append(f"{label}单选答案须为 A、B、C 或 D")
            elif part["options"]:
                issues.append(f"{label}简答题不应包含选项")
            stem = re.sub(r"\W", "", part["stem"]).casefold()
            if stem and any(SequenceMatcher(None, stem, old).ratio() >= 0.9 for old in stems):
                issues.append(f"{label}与本组已有题干过于相似，请修改")
            stems.append(stem)
        elif not part["title"].strip() or not part["content"].strip():
            issues.append(f"{label}需填写环节标题和讲解内容")
    return issues


def full_lesson_issues(body: dict) -> list[str]:
    issues = []
    for key, label in [("preparation", "课前准备"), ("homework", "课后巩固与参考要点")]:
        if not body.get(key, "").strip():
            issues.append(f"完整讲义需填写{label}")
    segments = body["segments"]
    stages = {part.get("stage", "instruction") for part in segments}
    missing_stages = set(LESSON_STAGES) - stages
    if missing_stages:
        issues.append(
            "完整讲义缺少环节："
            + "、".join(LESSON_STAGES[s] for s in LESSON_STAGES if s in missing_stages)
        )
    if segments[0].get("stage") != "opening" or segments[-1].get("stage") != "summary":
        issues.append("完整讲义应以导入开始、以总结检测结束")
    text_length = sum(len(re.sub(r"\s", "", part["content"])) for part in segments)
    minimum = lesson_minimum_chars(body["duration"])
    if text_length < minimum:
        issues.append(
            f"讲解正文需充分展开：当前 {text_length} 字，"
            f"{body['duration']} 分钟至少 {minimum} 字；请补充讲解、推导和具体示例"
        )
    if not any(part["example"].strip() for part in segments):
        issues.append("完整讲义至少需一份含题目、步骤和答案的例题演示")
    if not any(part.get("misconceptions", "").strip() for part in segments):
        issues.append("完整讲义需说明易错点及纠正方法")
    for index, part in enumerate(segments, 1):
        issues.extend(segment_issues(part, index))
    return issues


def render_markdown(kind: str, body: dict, node_names: dict[str, str] | None = None) -> str:
    names = node_names or {}
    lines = []
    if kind == "lesson":
        lines += [f"课时：{body['duration']} 分钟", "", "## 教学目标", body["objectives"], ""]
        if body["key_questions"]:
            lines += ["## 重点问题", body["key_questions"], ""]
        if body.get("format_version", 1) == 2:
            lines += ["## 课前准备", body.get("preparation", ""), "", "## 课堂安排", ""]
            elapsed = 0
            for part in body["segments"]:
                end = elapsed + part["minutes"]
                stage_label = LESSON_STAGES[part.get("stage", "instruction")]
                lines.append(f"- {elapsed}–{end} 分钟：{part['title']}（{stage_label}）")
                elapsed = end
            lines.append("")
    for index, part in enumerate(parts(kind, body), 1):
        if kind == "quiz":
            label = "单选题" if part["type"] == "single_choice" else "简答题"
            lines += [f"## {index}. {label}", "", part["stem"], ""]
            lines.extend(f"{letter}. {option}" for letter, option in zip("ABCD", part["options"]))
            lines += ["", f"**答案**：{part['answer']}", "", f"**解析**：{part['explanation']}"]
        else:
            lines += [f"## {index}. {part['title']} · {part['minutes']} 分钟", "", part["content"]]
            if part["activity"]:
                lines += ["", "### 教师引导与课堂活动", "", part["activity"]]
            if part["example"]:
                lines += ["", "### 例题与演示", "", part["example"]]
            for key, label in [
                ("student_activity", "学生任务"),
                ("expected_response", "预期回答与参考答案"),
                ("check_for_understanding", "检查与反馈"),
                ("misconceptions", "易错点与纠正"),
            ]:
                if part.get(key):
                    lines += ["", f"### {label}", "", part[key]]
            for quiz_id in part["quiz_ids"]:
                example = body.get("examples", {}).get(quiz_id)
                if example:
                    lines += [
                        "",
                        f"### 关联例题：{example['title']} · v{example['version']}",
                        example["answer"],
                    ]
        lines += ["", "知识点：" + "、".join(names.get(n, n) for n in part["node_ids"])]
        lines += ["依据：" + "、".join(part["citation_ids"]), ""]
    if kind == "lesson" and body.get("student_homework"):
        lines += ["## 学生版课后任务", "", body["student_homework"], ""]
    if kind == "lesson" and body.get("homework"):
        lines += ["## 课后巩固与参考要点", "", body["homework"], ""]
    if body["missing_info"]:
        lines += ["## 待补充", *[f"- {item}" for item in body["missing_info"]], ""]
    return "\n".join(lines)
