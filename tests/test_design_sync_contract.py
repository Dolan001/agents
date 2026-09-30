import pytest

from ai_workflow.design_fidelity import _resolver_contract
from ai_workflow.execution import _acquire_path_lease, _release_path_lease


@pytest.mark.parametrize("target", ["frontend", "mobile"])
@pytest.mark.parametrize("check_only,allow_update", [(False, False), (False, True), (True, False)])
def test_resolver_lease_matches_authorization(tmp_path, target, check_only, allow_update):
    contract = _resolver_contract(
        tmp_path, target, {}, [], check_only=check_only, allow_baseline_update=allow_update,
    )
    assert ("HTML/approved/**" in contract["allowed_paths"]) == allow_update
    assert ("HTML/approved/**" in contract["forbidden_paths"]) == (not allow_update)
    assert (f"apps/{target}/**" in contract["allowed_paths"]) == (not check_only)
    output = f".ai/evidence/design-fidelity/{target}/comparison.json"
    assert contract["expected_outputs"] == [output]
    _acquire_path_lease(tmp_path, contract)
    _release_path_lease(tmp_path, contract["task_id"])
