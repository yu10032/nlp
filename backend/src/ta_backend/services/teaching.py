"""两种教学内容的结构、审核条件与可读导出。草稿允许留白，签核检查完整性。"""

import re
from difflib import SequenceMatcher
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TeachingKind = Literal["quiz", "lesson"]


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
    title: str = Field(default="", max_length=200)
    minutes: int = Field(default=5, ge=1, le=240)
    content: str = Field(default="", max_length=6000)
    activity: str = Field(default="", max_length=2000)
    example: str = Field(default="", max_length=3000)
    quiz_ids: list[str] = Field(default_factory=list, max_length=5)


class LessonBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    duration: int = Field(default=45, ge=5, le=240)
    objectives: str = Field(default="", max_length=3000)
    key_questions: str = Field(default="", max_length=3000)
    segments: list[LessonSegment] = Field(min_length=1, max_length=12)
    missing_info: list[str] = Field(default_factory=list, max_length=20)


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


def render_markdown(kind: str, body: dict, node_names: dict[str, str] | None = None) -> str:
    names = node_names or {}
    lines = []
    if kind == "lesson":
        lines += [f"课时：{body['duration']} 分钟", "", "## 教学目标", body["objectives"], ""]
        if body["key_questions"]:
            lines += ["## 重点问题", body["key_questions"], ""]
    for index, part in enumerate(parts(kind, body), 1):
        if kind == "quiz":
            label = "单选题" if part["type"] == "single_choice" else "简答题"
            lines += [f"## {index}. {label}", "", part["stem"], ""]
            lines.extend(f"{letter}. {option}" for letter, option in zip("ABCD", part["options"]))
            lines += ["", f"**答案**：{part['answer']}", "", f"**解析**：{part['explanation']}"]
        else:
            lines += [f"## {index}. {part['title']} · {part['minutes']} 分钟", "", part["content"]]
            if part["activity"]:
                lines += ["", f"课堂活动：{part['activity']}"]
            if part["example"]:
                lines += ["", f"例子建议：{part['example']}"]
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
    if body["missing_info"]:
        lines += ["## 待补充", *[f"- {item}" for item in body["missing_info"]], ""]
    return "\n".join(lines)
