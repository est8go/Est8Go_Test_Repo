"""Dependency-free regression checks for follow-up task ownership."""

import ast
from pathlib import Path
import unittest


TASKS_ROUTER = Path(__file__).parents[1] / "app" / "operations" / "tasks_router.py"
PIPELINE_ROUTER = Path(__file__).parents[1] / "app" / "conversations" / "pipeline_router.py"


class TaskAssignmentContractTests(unittest.TestCase):
    def setUp(self):
        self.tasks_source = TASKS_ROUTER.read_text(encoding="utf-8")
        self.pipeline_source = PIPELINE_ROUTER.read_text(encoding="utf-8")
        self.tasks_tree = ast.parse(self.tasks_source)

    def test_task_router_remains_valid_python(self):
        self.assertIsInstance(self.tasks_tree, ast.Module)

    def test_manager_assignment_endpoint_and_audit_are_present(self):
        self.assertIn('@router.post("/{task_id}/assign")', self.tasks_source)
        self.assertIn("class AssignTaskRequest", self.tasks_source)
        self.assertIn("User.tenant_id == tenant_id", self.tasks_source)
        self.assertIn("User.is_active.is_(True)", self.tasks_source)
        self.assertIn('action="task_assigned" if previous_id is None else "task_reassigned"', self.tasks_source)

    def test_self_claim_uses_a_conditional_update(self):
        claim_start = self.tasks_source.index("async def claim_task")
        claim_source = self.tasks_source[claim_start:]
        self.assertIn("FollowUpTask.assigned_user_id.is_(None)", claim_source)
        self.assertIn(".update(", claim_source)
        self.assertIn('action="task_claimed"', claim_source)

    def test_pipeline_returns_an_explanation_for_each_temperature(self):
        self.assertIn("temperature_reason", self.pipeline_source)
        self.assertIn('"temperature_reason": temperature_reason', self.pipeline_source)


if __name__ == "__main__":
    unittest.main()
