from sqlalchemy import select
from sqlalchemy.orm import Session
from ta_backend.models import Question, QuestionBatch, QuestionGroup
from ta_backend.services.question_groups import similar_groups

ROOT = "/api/v1/courses/demo-nlp"
TEXTS = [
    "注意力机制如何对值向量加权求和？",
    "注意力机制怎样对值向量加权求和？",
    "注意力机制在机器翻译中如何使用？",
    "分词有哪些常见方法？",
    "分词有哪些常见方法",
    "考试几点开始？",
]


def create_batch(client, texts=TEXTS, title="第三周提问"):
    response = client.post(
        f"{ROOT}/question-batches",
        json={
            "title": title,
            "questions": [{"question_text": t, "method": "name"} for t in texts],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_batch_candidates_preserve_ids_predictions_and_distinct_intents(api):
    client, _ = api
    batch = create_batch(client)
    questions = batch["questions"]
    assert [q["text"] for q in questions] == TEXTS
    assert len({q["id"] for q in questions}) == 6
    assert all(q["batch_id"] == batch["id"] and q["needs_review"] for q in questions)
    assert questions[0]["predictions"] == questions[2]["predictions"]
    assert len(batch["groups"]) == 2
    assert {frozenset(g["question_ids"]) for g in batch["groups"]} == {
        frozenset(q["id"] for q in questions[:2]),
        frozenset(q["id"] for q in questions[3:5]),
    }
    assert all(g["status"] == "candidate" for g in batch["groups"])
    assert questions[2]["group_id"] is None and questions[5]["group_id"] is None
    assert client.get(f"{ROOT}/question-batches/{batch['id']}").json() == batch
    assert client.get(f"{ROOT}/question-batches").json()[0]["question_count"] == 6


def test_legacy_import_and_individual_history_remain_compatible(api):
    client, _ = api
    single = client.post(f"{ROOT}/questions/match", json={"question_text": "分词"}).json()
    assert single["batch_id"] is None and single["group_id"] is None
    legacy = client.post(
        f"{ROOT}/questions/batch",
        json={
            "questions": [{"question_text": "注意力"}, {"question_text": "考试时间"}],
        },
    ).json()
    assert isinstance(legacy, list) and len(legacy) == 2
    batch_id = legacy[0]["batch_id"]
    assert batch_id and legacy[1]["batch_id"] == batch_id
    assert len(client.get(f"{ROOT}/questions?batch_id={batch_id}").json()) == 2
    assert len(client.get(f"{ROOT}/questions").json()) == 3


def test_group_confirmation_correction_and_dissolve_do_not_relabel_questions(api):
    client, engine = api
    batch = create_batch(client)
    group = batch["groups"][0]
    raw = {q["id"]: q for q in batch["questions"]}
    payload = {"expected_version": 1, "question_ids": group["question_ids"], "title": "同一诉求"}
    updated = client.patch(f"{ROOT}/question-groups/{group['id']}", json=payload).json()
    saved = next(g for g in updated["groups"] if g["id"] == group["id"])
    assert saved["status"] == "confirmed" and saved["version"] == 2
    assert saved["proposal"] == group["proposal"]
    assert all(
        q["needs_review"] and q["predictions"] == raw[q["id"]]["predictions"]
        for q in updated["questions"]
    )
    assert client.patch(f"{ROOT}/question-groups/{group['id']}", json=payload).status_code == 409
    invalid = {**payload, "expected_version": 2, "question_ids": [group["question_ids"][0]] * 2}
    assert client.patch(f"{ROOT}/question-groups/{group['id']}", json=invalid).status_code == 422
    dissolved = client.delete(f"{ROOT}/question-groups/{group['id']}?expected_version=2").json()
    assert len(dissolved["questions"]) == len(raw)
    assert all(
        q["group_id"] is None for q in dissolved["questions"] if q["id"] in group["question_ids"]
    )
    with Session(engine) as session:
        assert session.get(QuestionGroup, group["id"]) is None
        assert all(session.get(Question, qid).family_id is None for qid in raw)


def test_manual_group_merge_and_removal_are_scoped_and_versioned(api):
    client, _ = api
    batch = create_batch(client)
    groups = batch["groups"]
    merge = client.post(
        f"{ROOT}/question-groups/merge",
        json={
            "group_ids": [g["id"] for g in groups],
            "expected_versions": {g["id"]: g["version"] for g in groups},
        },
    )
    assert merge.status_code == 200, merge.text
    group = merge.json()["groups"][0]
    assert len(group["question_ids"]) == 4 and group["status"] == "candidate"
    removed = group["question_ids"][0]
    update = client.patch(
        f"{ROOT}/question-groups/{group['id']}",
        json={
            "expected_version": group["version"],
            "question_ids": group["question_ids"][1:],
            "confirm": False,
        },
    ).json()
    assert next(q for q in update["questions"] if q["id"] == removed)["group_id"] is None
    assert update["groups"][0]["status"] == "candidate"
    # 手工将两个未归组问题整理为新组。
    free = [q["id"] for q in update["questions"] if not q["group_id"]]
    manual = client.post(
        f"{ROOT}/question-batches/{batch['id']}/groups",
        json={
            "question_ids": free[:2],
            "title": "教师整理",
        },
    )
    assert manual.status_code == 201
    assert any(
        g["title"] == "教师整理" and g["status"] == "confirmed" for g in manual.json()["groups"]
    )
    assert (
        client.post(
            f"{ROOT}/question-batches/{batch['id']}/groups", json={"question_ids": free[:2]}
        ).status_code
        == 409
    )


def test_foreign_courses_batches_and_groups_are_rejected(api):
    client, _ = api
    batch = create_batch(client)
    second = create_batch(client, title="第四周")
    other = client.post("/api/v1/courses", json={"title": "另一门课"}).json()["id"]
    root = f"/api/v1/courses/{other}"
    assert client.get(f"{root}/question-batches").json() == []
    assert client.get(f"{root}/question-batches/{batch['id']}").status_code == 404
    group = batch["groups"][0]
    payload = {"expected_version": group["version"], "question_ids": group["question_ids"]}
    assert client.patch(f"{root}/question-groups/{group['id']}", json=payload).status_code == 404
    assert (
        client.delete(f"{root}/question-groups/{group['id']}?expected_version=1").status_code == 404
    )
    assert client.get(f"{root}/questions?batch_id={batch['id']}").status_code == 404
    ids = [g["id"] for g in [group, second["groups"][0]]]
    assert (
        client.post(
            f"{ROOT}/question-groups/merge",
            json={"group_ids": ids, "expected_versions": dict.fromkeys(ids, 1)},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{ROOT}/question-batches/{second['id']}/groups",
            json={
                "question_ids": [q["id"] for q in batch["questions"][-2:]],
            },
        ).status_code
        == 409
    )


def test_failed_batch_is_atomic_and_does_not_leave_partial_records(api):
    client, engine = api
    response = client.post(
        f"{ROOT}/question-batches",
        json={
            "questions": [
                {"question_text": "分词", "method": "name"},
                {"question_text": "分词", "method": "mlp"},
            ]
        },
    )
    assert response.status_code == 409
    with Session(engine) as session:
        assert session.scalar(select(QuestionBatch)) is None
        assert session.scalar(select(Question)) is None


def test_complete_link_does_not_chain_different_intents():
    # 两端均与中间问题相似，但两端互不相似，不能把三者串为同组。
    result = similar_groups(["alpha beta", "alpha beta gamma delta", "gamma delta"], 0.5)
    assert len(result) == 1 and len(result[0]["indices"]) == 2
    assert similar_groups(["？", "！！！"]) == []
