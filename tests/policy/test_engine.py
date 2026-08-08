from safepatch.core.models import parse_action
from safepatch.policy.engine import DecisionStatus, PolicyEngine


def test_dangerous_check_name_is_denied():
    action = parse_action({"type": "run_check", "name": "rm -rf /"})

    decision = PolicyEngine(allowed_checks={"unit-test"}).evaluate(action)

    assert decision.status == DecisionStatus.DENY
    assert "dangerous command" in decision.reason


def test_non_allowlisted_check_is_denied():
    action = parse_action({"type": "run_check", "name": "deploy"})

    decision = PolicyEngine(allowed_checks={"unit-test"}).evaluate(action)

    assert decision.status == DecisionStatus.DENY
    assert decision.reason == "check is not allowlisted: deploy"


def test_allowlisted_check_is_allowed():
    action = parse_action({"type": "run_check", "name": "unit-test"})

    decision = PolicyEngine(allowed_checks={"unit-test"}).evaluate(action)

    assert decision.status == DecisionStatus.ALLOW


def test_sensitive_read_is_denied():
    action = parse_action({"type": "read_file", "path": ".env"})

    decision = PolicyEngine().evaluate(action)

    assert decision.status == DecisionStatus.DENY
    assert "sensitive path" in decision.reason


def test_protected_patch_requires_approval():
    action = parse_action(
        {
            "type": "apply_patch",
            "patch": """--- a/package-lock.json
+++ b/package-lock.json
@@ -1 +1 @@
-old
+new
""",
        }
    )

    decision = PolicyEngine(protected_paths={"package-lock.json"}).evaluate(action)

    assert decision.status == DecisionStatus.REQUIRES_APPROVAL
    assert decision.reason == "protected path requires approval: package-lock.json"
