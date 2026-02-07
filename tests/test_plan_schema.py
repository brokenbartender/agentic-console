import os
import sys
import time
import unittest
from dataclasses import asdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.schemas import PlanSchema, PlanStepSchema, VerifySchema, Budget


class TestPlanSchema(unittest.TestCase):
    def test_plan_schema_defaults(self):
        step = PlanStepSchema(
            step_id=1,
            title="Gather context",
            intent="Collect inputs",
            tool="shell",
            args={"cmd": "echo hello"},
        )
        plan = PlanSchema(
            run_id="run-1",
            trace_id="trace-1",
            goal="Test plan",
            success_criteria=["done"],
            steps=[step],
            created_at=time.time(),
            model="test-model",
        )
        self.assertEqual(plan.budget.max_steps, 20)
        self.assertEqual(plan.needs_user_input, False)
        self.assertEqual(plan.steps[0].risk, "safe")
        payload = asdict(plan)
        self.assertEqual(payload["goal"], "Test plan")
        self.assertEqual(payload["steps"][0]["tool"], "shell")

    def test_plan_step_with_verify_and_fallback(self):
        verify = VerifySchema(type="file_exists", params={"path": "README.md"})
        fallback = PlanStepSchema(
            step_id=2,
            title="Fallback",
            intent="Handle missing file",
            tool="shell",
            args={"cmd": "dir"},
        )
        step = PlanStepSchema(
            step_id=1,
            title="Check file",
            intent="Ensure file exists",
            tool="shell",
            args={"cmd": "dir README.md"},
            verify=verify,
            fallback=fallback,
            requires_confirmation=True,
        )
        self.assertTrue(step.requires_confirmation)
        self.assertEqual(step.verify.type, "file_exists")
        self.assertEqual(step.fallback.step_id, 2)


if __name__ == "__main__":
    unittest.main()
