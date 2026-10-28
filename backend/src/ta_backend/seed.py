"""显式导入演示数据；应用启动不会自动写入示例或建表。"""

import json

from sqlalchemy.orm import Session

from ta_backend.config import PROJECT_ROOT, Settings
from ta_backend.db import make_engine
from ta_backend.models import Chunk, Course, KnowledgeEdge, KnowledgeNode, Material, NodeEvidence


def seed_demo(session: Session) -> bool:
    data = json.loads((PROJECT_ROOT / "data/sample/course.json").read_text(encoding="utf-8"))
    course_id = data["id"]
    if session.get(Course, course_id):
        return False
    session.add(Course(id=course_id, title=data["title"], description=data["description"]))
    session.flush()
    session.add(Material(id="demo-material", course_id=course_id, title=data["material_title"]))
    session.flush()
    session.add_all(
        Chunk(course_id=course_id, material_id="demo-material", **chunk) for chunk in data["chunks"]
    )
    session.add_all(
        KnowledgeNode(
            id=node["id"],
            course_id=course_id,
            name=node["name"],
            aliases=node["aliases"],
            description=node["description"],
            kind=node["kind"],
            status="confirmed",
        )
        for node in data["nodes"]
    )
    session.flush()
    session.add_all(
        NodeEvidence(course_id=course_id, node_id=node["id"], chunk_id=chunk_id)
        for node in data["nodes"]
        for chunk_id in node["chunk_ids"]
    )
    session.add_all(
        KnowledgeEdge(course_id=course_id, status="confirmed", **edge) for edge in data["edges"]
    )
    session.commit()
    return True


def main():
    engine = make_engine(Settings.from_env().database_url)
    with Session(engine) as session:
        created = seed_demo(session)
    engine.dispose()
    print("已导入示例课程" if created else "示例课程已存在，保留现有数据")


if __name__ == "__main__":
    main()
