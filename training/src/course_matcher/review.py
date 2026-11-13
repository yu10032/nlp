"""离线双人标注复核；不调用模型，不替代人工签核。"""

import argparse
import json
import sqlite3
import unicodedata
from pathlib import Path

from course_matcher.data import read_pairs


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_rows(path: Path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )


def text_key(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFKC", text).casefold()
        if not c.isspace() and not unicodedata.category(c).startswith("P")
    )


def require_text(row: dict, field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{row.get('id', '记录')} 缺少 {field}")
    return value.strip()


def index_rows(rows: list[dict]) -> dict[str, dict]:
    result = {}
    for row in rows:
        key = require_text(row, "id")
        if key in result:
            raise ValueError(f"问题 ID 重复：{key}")
        require_text(row, "question")
        result[key] = row
    if not result:
        raise ValueError("问题文件为空；请先收集实际问题")
    return result


def check_duplicate_families(rows: list[dict]):
    families = {}
    for row in rows:
        key = text_key(row["question"])
        family = row["family_id"].strip()
        if key in families and families[key] != family:
            raise ValueError(f"重复问题被分入不同家族：{row['id']}")
        families[key] = family


def check_classroom(rows: list[dict], course_id: str, excluded: list[dict]):
    """来源声明及文本重复检查不能替代人工排查改写和同源问题。"""
    used_text = {text_key(row["question"]) for row in excluded}
    used_ids = {row["id"] for row in excluded}
    used_families = {row["family_id"] for row in excluded}
    for row in rows:
        source = row.get("source")
        if not isinstance(source, dict) or source.get("kind") != "classroom":
            raise ValueError(f"{row['id']} 缺少真实课堂来源")
        for field in ("session", "record_id"):
            require_text(source, field)
        if source.get("course_id") != course_id:
            raise ValueError(f"{row['id']} 的来源课程与冻结图谱不符")
        if source.get("deidentified") is not True:
            raise ValueError(f"{row['id']} 尚未声明已脱敏")
        if source.get("used_in_development") is not False:
            raise ValueError(f"{row['id']} 必须明确未用于开发或调参")
        if (
            text_key(row["question"]) in used_text
            or row["id"] in used_ids
            or row["family_id"] in used_families
        ):
            raise ValueError(f"{row['id']} 与已有开发数据重复或同家族，不能作为独立评价题")


def attach_evidence(snapshot: dict, database: Path) -> list[dict]:
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        course = connection.execute(
            "select graph_version from courses where id=?", (snapshot["course_id"],)
        ).fetchone()
        if course is None or course[0] != snapshot["graph_version"]:
            raise ValueError("当前课程图谱版本与冻结快照不符，请先明确复核范围")
        nodes = []
        for node in snapshot["nodes"]:
            live = connection.execute(
                "select name,aliases,description from knowledge_nodes "
                "where course_id=? and id=? and status='confirmed' and kind!='chapter'",
                (snapshot["course_id"], node["id"]),
            ).fetchone()
            if live is None or (live["name"], json.loads(live["aliases"]), live["description"]) != (
                node["name"],
                node["aliases"],
                node["description"],
            ):
                raise ValueError(f"节点已变化：{node['id']}，请先明确复核范围")
            evidence = connection.execute(
                "select c.id,c.text,c.locator,m.title,m.version from node_evidence e "
                "join chunks c on c.id=e.chunk_id and c.course_id=e.course_id "
                "join materials m on m.id=c.material_id and m.course_id=c.course_id "
                "where e.course_id=? and e.node_id=? and m.active=1 order by c.position,c.id",
                (snapshot["course_id"], node["id"]),
            ).fetchall()
            if not evidence:
                raise ValueError(f"节点缺少有效课程依据：{node['id']}")
            nodes.append({**node, "evidence": [dict(row) for row in evidence]})
    return nodes


def render_page(path: Path, packet: dict, slot: str, questions: list[dict], peers=None):
    payload = {
        "packet_id": packet["packet_id"],
        "slot": slot,
        "dataset_version": packet["dataset_version"],
        "origin": packet["origin"],
        "course_id": packet["course_id"],
        "graph_version": packet["graph_version"],
        "nodes": packet["nodes"],
        "questions": questions,
        "peers": peers or {},
        "family_questions": packet["questions"],
    }
    # 数据只能作为 JSON 读取，不能闭合 script 或进入 HTML 模板。
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("review_page.html").read_text(encoding="utf-8")
    path.write_text(template.replace("__REVIEW_PAYLOAD__", encoded), encoding="utf-8")


def prepare(
    source: Path,
    nodes_file: Path,
    database: Path,
    output: Path,
    dataset_version: str,
    origin: str = "development",
    exclude: list[Path] | None = None,
):
    rows = read_pairs(source)
    index_rows(rows)
    for row in rows:
        require_text(row, "family_id")
    check_duplicate_families(rows)
    snapshot = json.loads(nodes_file.read_text(encoding="utf-8"))
    excluded = []
    if origin != "classroom" and any(
        row.get("split_role") == "heldout"
        or (isinstance(row.get("source"), dict) and row["source"].get("kind") == "classroom")
        for row in rows
    ):
        raise ValueError("课堂评价题必须使用 --origin classroom，不能改作普通开发复核")
    if origin == "classroom":
        if not exclude:
            raise ValueError("真实课堂评价题需要 --exclude 指定已用于开发的数据")
        excluded = [row for path in exclude for row in read_pairs(path)]
        check_classroom(rows, snapshot["course_id"], excluded)
    packet = {
        "packet_id": output.name,
        "dataset_version": dataset_version,
        "origin": origin,
        "course_id": snapshot["course_id"],
        "graph_version": snapshot["graph_version"],
        "nodes": attach_evidence(snapshot, database),
        "excluded_families": sorted({row["family_id"] for row in excluded}),
        "questions": [{key: row[key] for key in ("id", "question", "family_id")} for row in rows],
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "packet.json", packet)
    write_rows(output / "original.jsonl", rows)
    for slot in ("a", "b"):
        render_page(output / f"review-{slot}.html", packet, slot, packet["questions"])
    return {"questions": len(rows), "families": len({r["family_id"] for r in rows})}


def read_review(packet: dict, path: Path, slot: str, questions: list[dict]) -> dict[str, dict]:
    records = index_rows(read_pairs(path))
    expected = {row["id"]: row for row in questions}
    if records.keys() != expected.keys():
        raise ValueError(f"{slot} 的问题集合不符，缺失或额外的 ID 必须处理后重交")
    valid_nodes = {node["id"] for node in packet["nodes"]}
    for key, record in records.items():
        if record.get("packet_id") != packet["packet_id"] or record.get("slot") != slot:
            raise ValueError(f"{slot} 的复核包或角色不符：{key}")
        if record["question"] != expected[key]["question"]:
            raise ValueError(f"{slot} 的问题正文已变化：{key}")
        if record.get("decision") != "confirmed":
            raise ValueError(f"{slot} 尚未确认：{key}")
        for field in ("reviewer", "rationale", "family_id"):
            require_text(record, field)
        ids = record.get("node_ids")
        if (
            not isinstance(ids, list)
            or not all(isinstance(n, str) for n in ids)
            or len(ids) != len(set(ids))
            or not set(ids).issubset(valid_nodes)
        ):
            raise ValueError(f"{slot} 的知识点标签无效：{key}")
        if not isinstance(record.get("no_match"), bool) or record["no_match"] != (not ids):
            raise ValueError(f"{slot} 必须明确选择知识点或无关联：{key}")
    reviewers = {record["reviewer"].strip().casefold() for record in records.values()}
    if len(reviewers) != 1:
        raise ValueError(f"{slot} 应由同一名独立复核人完成")
    return records


def reviews(packet: dict, a_file: Path, b_file: Path):
    a = read_review(packet, a_file, "a", packet["questions"])
    b = read_review(packet, b_file, "b", packet["questions"])
    if next(iter(a.values()))["reviewer"].strip().casefold() == (
        next(iter(b.values()))["reviewer"].strip().casefold()
    ):
        raise ValueError("A、B 必须由两名不同的复核人分别完成")
    conflicts = [
        row
        for row in packet["questions"]
        if (
            set(a[row["id"]]["node_ids"]) != set(b[row["id"]]["node_ids"])
            or a[row["id"]]["family_id"].strip() != b[row["id"]]["family_id"].strip()
        )
    ]
    return a, b, conflicts


def compare(packet_dir: Path, a_file: Path, b_file: Path, output: Path):
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    a, b, conflicts = reviews(packet, a_file, b_file)
    peers = {row["id"]: {"a": a[row["id"]], "b": b[row["id"]]} for row in conflicts}
    report = {
        "packet_id": packet["packet_id"],
        "questions": len(a),
        "label_agreements": sum(set(a[k]["node_ids"]) == set(b[k]["node_ids"]) for k in a),
        "family_agreements": sum(a[k]["family_id"].strip() == b[k]["family_id"].strip() for k in a),
        "conflicts": peers,
    }
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "comparison.json", report)
    if conflicts:
        render_page(output / "adjudication.html", packet, "adjudication", conflicts, peers)
    return {"questions": len(a), "conflicts": len(conflicts)}


def finalize(
    packet_dir: Path,
    a_file: Path,
    b_file: Path,
    output: Path,
    dataset_version: str,
    adjudication: Path | None = None,
):
    packet = json.loads((packet_dir / "packet.json").read_text(encoding="utf-8"))
    if not dataset_version.strip() or dataset_version == packet["dataset_version"]:
        raise ValueError("复核结果必须使用新的数据版本")
    original = read_pairs(packet_dir / "original.jsonl")
    originals = index_rows(original)
    if originals.keys() != {q["id"] for q in packet["questions"]} or any(
        originals[q["id"]]["question"] != q["question"] for q in packet["questions"]
    ):
        raise ValueError("原始问题快照与复核包不符，请重新准备")
    a, b, conflicts = reviews(packet, a_file, b_file)
    decisions = {}
    if conflicts:
        if adjudication is None:
            raise ValueError(f"仍有 {len(conflicts)} 条分歧，需要第三人裁决")
        decisions = read_review(packet, adjudication, "adjudication", conflicts)
        reviewers = {
            next(iter(review.values()))["reviewer"].strip().casefold() for review in (a, b)
        }
        if any(row["reviewer"].strip().casefold() in reviewers for row in decisions.values()):
            raise ValueError("裁决人应与两名复核人不同")
    elif adjudication is not None:
        raise ValueError("没有分歧，不应提交裁决记录")
    result = []
    for row in original:
        key = row["id"]
        choice = decisions.get(key, a[key])
        result.append(
            {
                **row,
                "family_id": choice["family_id"].strip(),
                "node_ids": sorted(choice["node_ids"]),
                "label_status": "confirmed",
                "reviewer": " / ".join(
                    dict.fromkeys(
                        r["reviewer"].strip()
                        for r in [a[key], b[key], *([decisions[key]] if key in decisions else [])]
                    )
                ),
                "rationale": choice["rationale"].strip(),
                "review": {"a": a[key], "b": b[key], "adjudication": decisions.get(key)},
                **({"split_role": "heldout"} if packet["origin"] == "classroom" else {}),
            }
        )
    if packet["origin"] == "classroom":
        # 人工纠正后的家族也不能回到已有开发家族。
        check_classroom(result, packet["course_id"], [])
        if any(row["family_id"] in packet["excluded_families"] for row in result):
            raise ValueError("纠正后的问题家族与开发数据重叠，不能作为独立评价题")
    check_duplicate_families(result)
    output.mkdir(parents=True, exist_ok=False)
    write_rows(output / "questions.jsonl", result)
    write_json(
        output / "nodes.json", {k: packet[k] for k in ("course_id", "graph_version", "nodes")}
    )
    write_json(
        output / "dataset.json",
        {
            "dataset_version": dataset_version,
            "source_version": packet["dataset_version"],
            "packet_id": packet["packet_id"],
            "origin": packet["origin"],
            "data_status": "development" if packet["origin"] == "development" else "heldout",
            "purpose": "reviewed_development"
            if packet["origin"] == "development"
            else "independent_evaluation_only",
            "questions": len(result),
            "families": len({r["family_id"] for r in result}),
            "resolved_conflicts": len(conflicts),
            "note": "签核依据为操作者填写的复核记录；工具不验证人员身份或教学判断。",
        },
    )
    return {"questions": len(result), "resolved_conflicts": len(conflicts)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="生成两份不含开发标签的离线复核页面")
    prep.add_argument("--input", type=Path, required=True)
    prep.add_argument("--nodes", type=Path, required=True)
    prep.add_argument("--database", type=Path, default=Path("data/runtime/assistant.db"))
    prep.add_argument("--origin", choices=["development", "classroom"], default="development")
    prep.add_argument("--exclude", type=Path, action="append")
    prep.add_argument("--dataset-version", required=True)
    prep.add_argument("--output", type=Path, required=True)
    for command in ("compare", "finalize"):
        sub = commands.add_parser(command)
        sub.add_argument("--packet", type=Path, required=True)
        sub.add_argument("--a", type=Path, required=True)
        sub.add_argument("--b", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
        if command == "finalize":
            sub.add_argument("--dataset-version", required=True)
            sub.add_argument("--adjudication", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(
                args.input,
                args.nodes,
                args.database,
                args.output,
                args.dataset_version,
                args.origin,
                args.exclude,
            )
        elif args.command == "compare":
            result = compare(args.packet, args.a, args.b, args.output)
        else:
            result = finalize(
                args.packet, args.a, args.b, args.output, args.dataset_version, args.adjudication
            )
    except (ValueError, FileExistsError) as error:
        parser.exit(2, f"{error}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
