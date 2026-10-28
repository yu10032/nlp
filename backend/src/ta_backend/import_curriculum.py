"""显式导入用户提供的知识体系原件及手工整理的教学草稿，不随服务启动执行。"""

import argparse
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from ta_backend.api.teaching import TeachingCreate, write_content
from ta_backend.config import Settings
from ta_backend.db import make_engine
from ta_backend.models import (
    Chunk,
    Course,
    KnowledgeEdge,
    KnowledgeNode,
    Material,
    NodeEvidence,
    TeachingContent,
)
from ta_backend.services.parsing import PARSER_VERSION, parse_file, validate_file

COURSE_ID = "nlp-curriculum"
# 这是开发时对照原文手工整理的范围，不把全部标题自动当成已确认图谱。
TOPICS = {
    "8.1": ("词法分析", "chapter", "对词的形态结构与语法功能进行分析。"),
    "8.1.1.2": ("汉语切分", "task", "将汉字序列按分词单位切分成词语序列。"),
    "8.1.1.3": ("子词切割", "method", "学习子词词表并据此切分字符串，缓解未登录词问题。"),
    "8.3": ("语言模型", "chapter", "为词序列建立概率模型，估计序列或下一个词的概率。"),
    "8.3.1": ("统计语言模型", "model", "描述自然语言概率分布，可计算词序列概率或预测后续词。"),
    "8.3.1.1": ("N元语言模型", "model", "引入马尔可夫假设，以前 n−1 个词近似当前词的历史依赖。"),
    "8.3.1.2": ("数据平滑", "method", "缓解语料稀疏导致的未见 N-gram 零概率问题。"),
    "8.3.1.3": ("语言模型性能评价", "metric", "困惑度用于内部评价，仍需结合具体下游任务表现。"),
    "8.3.2": ("神经网络语言模型", "model", "将神经网络引入语言建模，学习词的分布式表示。"),
    "8.3.2.1": ("前馈神经网络语言模型", "model", "以固定大小的上下文及词的分布式表示预测词。"),
    "8.3.2.2": (
        "循环神经网络语言模型",
        "model",
        "通过循环状态建模变长输入与时序信息，训练可能遇到梯度问题。",
    ),
    "8.3.3": ("预训练语言模型", "model", "通过预训练获得可用于自然语言处理任务的语言表征。"),
    "8.3.3.1": ("预训练范式", "concept", "区分静态词嵌入与依上下文生成表征的预训练编码器。"),
    "8.3.3.2": ("预训练任务", "concept", "以监督或自监督的辅助任务学习适用于下游任务的表征。"),
}


def import_curriculum(source: Path, settings: Settings):
    validate_file(source.name, source.read_bytes())
    parsed = parse_file(source)
    engine = make_engine(settings.database_url)
    with Session(engine, expire_on_commit=False) as session:
        if session.get(Course, COURSE_ID):
            print("知识体系课程已存在，保留已有资料和教学编辑；新版请在资料页上传。")
            return
        course = Course(
            id=COURSE_ID,
            title="自然语言处理 · 知识体系",
            description="用户提供的 NLP 知识体系原文；教学草稿须经教师审核。",
        )
        session.add(course)
        session.flush()
        destination = settings.storage_dir / COURSE_ID / "nlp-curriculum.docx"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        material = Material(
            course_id=COURSE_ID,
            title=source.stem,
            filename=source.name,
            storage_path=str(destination.resolve()),
            status="partial" if parsed.warnings else "ready",
            parser_version=PARSER_VERSION,
            warnings=parsed.warnings,
        )
        session.add(material)
        session.flush()
        chunks = []
        for index, part in enumerate(parsed.chunks):
            chunk = Chunk(
                course_id=COURSE_ID,
                material_id=material.id,
                text=part.text,
                locator=part.locator,
                section_path=part.section_path,
                position=index,
                paragraph_locator=part.paragraph_locator,
            )
            session.add(chunk)
            chunks.append(chunk)
        session.flush()
        topic_chunks = {}
        for code, (name, kind, description) in TOPICS.items():
            matching = [
                c
                for c in chunks
                if c.section_path and c.section_path[-1].split()[0] == code and len(c.text) > 25
            ]
            topic_chunks[code] = matching
            if not matching:
                raise ValueError(f"原件缺少 {code} 的可用正文，请核对版本")
            session.add(
                KnowledgeNode(
                    id=f"curriculum-{code}",
                    course_id=COURSE_ID,
                    name=name,
                    kind=kind,
                    description=description,
                    status="confirmed",
                    aliases={
                        "8.3.1.1": ["n-gram", "N-gram"],
                        "8.3.1.3": ["困惑度", "PPL"],
                        "8.3.2.1": ["FFNNLM"],
                        "8.3.2.2": ["RNNLM"],
                    }.get(code, []),
                )
            )
        session.flush()
        for code, matching in topic_chunks.items():
            session.add_all(
                NodeEvidence(course_id=COURSE_ID, node_id=f"curriculum-{code}", chunk_id=c.id)
                for c in matching
            )
            parent = code.rsplit(".", 1)[0]
            if parent not in TOPICS and len(code.split(".")) > 2:
                parent = ".".join(code.split(".")[:2])
            if parent in TOPICS:
                session.add(
                    KnowledgeEdge(
                        course_id=COURSE_ID,
                        source_id=f"curriculum-{parent}",
                        target_id=f"curriculum-{code}",
                        relation="contains",
                        chunk_id=matching[0].id,
                        status="confirmed",
                    )
                )
        session.commit()

        def links(code, index=0):
            return {
                "node_ids": [f"curriculum-{code}"],
                "citation_ids": [topic_chunks[code][index].id],
            }

        quiz = {
            "difficulty": "basic",
            "missing_info": [],
            "items": [
                {
                    "type": "single_choice",
                    "stem": "在 N 元语言模型的马尔可夫假设下，当前词依赖哪部分历史？",
                    "options": [
                        "前 n−1 个词",
                        "仅后一个词",
                        "完整历史且不作近似",
                        "始终不依赖历史",
                    ],
                    "answer": "A",
                    "explanation": "N 元模型以前 n−1 个词近似历史；例如 bigram 仅依赖前一个词。",
                    **links("8.3.1.1", 2),
                },
                {
                    "type": "short_answer",
                    "stem": (
                        "训练中未出现的 N-gram 是否意味着它在真实语言中的概率为零？"
                        "为什么需要数据平滑？"
                    ),
                    "options": [],
                    "answer": "不意味着。有限语料存在稀疏性，平滑用于缓解未见组合的零概率问题。",
                    "explanation": "原文区分未观测与不可能，并列举折扣法、加1平滑等策略。",
                    **links("8.3.1.2"),
                },
                {
                    "type": "short_answer",
                    "stem": "为什么不能仅凭困惑度更低，就断言模型在所有下游任务上更好？",
                    "options": [],
                    "answer": (
                        "困惑度属于语言模型内部评价，不能保证下游任务性能，应在具体任务上另作评价。"
                    ),
                    "explanation": "原文明确说明困惑度低不一定带来更好的外部任务表现。",
                    **links("8.3.1.3"),
                },
            ],
        }
        targets = [f"curriculum-{code}" for code in ("8.3.1.1", "8.3.1.2", "8.3.1.3")]
        write_content(
            TeachingContent(
                course_id=COURSE_ID,
                kind="quiz",
                version=1,
                body={},
                generation_info={"provider": "manual", "source": source.name},
            ),
            TeachingCreate(title="语言模型基础练习", target_node_ids=targets, body=quiz),
            "quiz",
            COURSE_ID,
            session,
        )
        segments = [
            {
                "title": "从上下文预测引入 N 元模型",
                "minutes": 10,
                "content": (
                    "对照 unigram、bigram 与 trigram 的历史窗口，说明马尔可夫近似及复杂度取舍。"
                ),
                "activity": "让学生指出三元模型预测当前词时需要哪些历史词。",
                "example": "用一个短句标出前两个词与待预测位置。",
                **links("8.3.1.1", 2),
            },
            {
                "title": "语料稀疏与平滑",
                "minutes": 15,
                "content": "区分未观察到的组合与不可能的组合，解释零概率问题及数据平滑的动机。",
                "activity": "讨论小规模语料中未出现的合理表达。",
                "example": "比较见过的词组合与一个未见但合理的组合。",
                **links("8.3.1.2"),
            },
            {
                "title": "困惑度与任务评价",
                "minutes": 12,
                "content": "介绍困惑度的内部评价定位，讨论其与下游任务表现的关系与局限。",
                "activity": "讨论是否可以仅凭更低的困惑度选择部署模型。",
                "example": "提出两个内部评价与任务指标排序不同的假设结果供讨论。",
                **links("8.3.1.3"),
            },
            {
                "title": "回顾与随堂检查",
                "minutes": 8,
                "content": "回顾上下文窗口、数据平滑与内部评价三个概念的边界。",
                "activity": "按课程题库中的三道基础题开展随堂检查，使用前先审核题组。",
                "example": "由教师选取学生回答中的常见混淆进行讲解。",
                "node_ids": targets,
                "citation_ids": [topic_chunks[c][0].id for c in ("8.3.1.1", "8.3.1.2", "8.3.1.3")],
            },
        ]
        for segment in segments:
            segment["quiz_ids"] = []
        write_content(
            TeachingContent(
                course_id=COURSE_ID,
                kind="lesson",
                version=1,
                body={},
                generation_info={"provider": "manual", "source": source.name},
            ),
            TeachingCreate(
                title="统计语言模型入门",
                target_node_ids=targets,
                body={
                    "duration": 45,
                    "objectives": (
                        "解释 N 元模型的上下文假设，说明平滑的动机，并区分内部评价与下游任务评价。"
                    ),
                    "key_questions": "未见过是否等于不可能？困惑度更低是否一定更好？",
                    "segments": segments,
                    "missing_info": ["按实际学情调整环节时长与例子；题组审核后再关联为课堂例题。"],
                },
            ),
            "lesson",
            COURSE_ID,
            session,
        )
        print(f"已导入 {len(chunks)} 段原文、{len(TOPICS)} 个来源核对节点、题组和45分钟备课草稿。")
        for warning in parsed.warnings:
            print("原件提示：" + warning)
    engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    import_curriculum(args.source.resolve(), Settings.from_env())


if __name__ == "__main__":
    main()
