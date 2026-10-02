from ai_workflow.execution import _phase_requires_capability_evidence
from ai_workflow.io import write_json

TERMS = ("rag", "citation", "retrieval")


def test_capability_evidence_follows_phase_task_scope(tmp_path):
    write_json(tmp_path / ".ai/task-queue.json", {"tasks": [
        {
            "task_id": "TASK-PUBLIC-WEB", "feature_id": "public-web",
            "agent": "react-implementer", "description": "Public pages and storage policy",
            "allowed_paths": ["apps/frontend/**"], "dependencies": [],
        },
        {
            "task_id": "TASK-CHAT-MOBILE", "feature_id": "chat-mobile",
            "agent": "flutter-implementer", "description": "RAG citations",
            "allowed_paths": ["apps/mobile/**"], "dependencies": [],
        },
    ]})
    assert not _phase_requires_capability_evidence(tmp_path, "frontend", TERMS)
    assert _phase_requires_capability_evidence(tmp_path, "mobile", TERMS)


def test_capability_evidence_remains_fail_closed_without_tasks(tmp_path):
    assert _phase_requires_capability_evidence(tmp_path, "frontend", TERMS)
