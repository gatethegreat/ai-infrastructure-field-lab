"""Run one bounded paid Dapr Agents model/tool/approval smoke path."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import time

from dapr.ext.workflow import DaprWorkflowClient
from dapr_agents.agents.schemas import ApprovalResponseEvent
from dapr_agents.workflow.runners import AgentRunner

from incident_runtime import IncidentToolRuntime, build_agent


async def run(decision: str) -> dict[str, object]:
    runtime = IncidentToolRuntime()
    agent = build_agent(runtime)
    runner = AgentRunner()
    workflow_client = DaprWorkflowClient()
    started_at = datetime.now(UTC).isoformat()
    try:
        instance_id = await runner.run(
            agent,
            payload={
                "task": (
                    "Handle the supplied synthetic incident. Inspect it first, then use "
                    "only the permitted simulated remediation."
                ),
                "incident": runtime.fixture["incident"],
            },
            wait=False,
        )
        deadline = time.monotonic() + 90
        approval = None
        while time.monotonic() < deadline:
            pending = agent.list_pending_approvals()
            if pending:
                approval = pending[0]
                break
            await asyncio.sleep(0.5)
        if approval is None:
            raise TimeoutError("no approval request appeared within 90 seconds")

        approved = decision == "approve"
        request_id = approval["approval_request_id"]
        response = ApprovalResponseEvent(
            approval_request_id=request_id,
            approved=approved,
            reason=f"synthetic smoke decision: {decision}",
        )
        workflow_client.raise_workflow_event(
            instance_id=approval["instance_id"],
            event_name=f"approval_response_{request_id}",
            data=response.model_dump(mode="json"),
        )
        state = await asyncio.to_thread(
            runner.wait_for_workflow_completion,
            instance_id,
            timeout_in_seconds=120,
        )
        return {
            "captured_at": datetime.now(UTC).isoformat(),
            "started_at": started_at,
            "experiment": "03-dapr-agents",
            "provider_path": "Dapr conversation.openai",
            "model": "gpt-5.6-luna",
            "decision": decision,
            "instance_id": instance_id,
            "approval": {
                "step_name": approval["step_name"],
                "tool_arguments": approval["tool_arguments"],
                "approval_request_id": request_id,
            },
            "runtime_calls": runtime.calls,
            "effect_count": runtime.executor.effect_count,
            "workflow_output": getattr(state, "serialized_output", None),
        }
    finally:
        workflow_client.close()
        runner.shutdown(agent)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision", choices=("approve", "deny"), default="approve")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    evidence = asyncio.run(run(args.decision))
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
