from pathlib import Path
from unittest.mock import Mock, patch

from ai_workflow.execution import _run_adapter


def test_argument_prompt_transport_appends_prompt(tmp_path: Path) -> None:
    config = {
        "adapters": {
            "cursor": {
                "argv": ["agent", "-p", "--output-format", "text"],
                "prompt_transport": "argument",
            }
        },
        "timeout_seconds": 10,
    }
    completed = Mock(returncode=0, stdout="done", stderr="")

    with (
        patch("ai_workflow.execution.read_json", return_value=config),
        patch("ai_workflow.execution.shutil.which", return_value="/usr/local/bin/agent"),
        patch("ai_workflow.provider_selection.refresh_provider_projection"),
        patch("ai_workflow.execution.subprocess.run", return_value=completed) as run,
    ):
        result = _run_adapter(tmp_path, "cursor", "follow this workflow")

    assert result["returncode"] == 0
    assert run.call_args.args[0][-1] == "follow this workflow"
    assert run.call_args.kwargs["input"] is None
