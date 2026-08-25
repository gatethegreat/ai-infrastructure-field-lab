"""Deterministic crash/restart probe for the Dapr workflow beneath Dapr Agents."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import timedelta
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dapr.clients import DaprClient
from dapr.ext.workflow import (
    DaprWorkflowClient,
    DaprWorkflowContext,
    RetryPolicy,
    WorkflowActivityContext,
    WorkflowRuntime,
)

from shared.contracts import ActionRequest, Incident
from shared.fixtures import load_scenario
from shared.tools import FixtureRepository, IncidentContextTool


WORKFLOW_NAME = "shared_incident_recovery_v1"
STATE_STORE = "agent-memory"
_inspection_attempts = 0


def _inspection_key(instance_id: str) -> str:
    return f"recovery-probe:{instance_id}:inspection"


def _effect_key(delivery_id: str) -> str:
    return f"recovery-probe:effect:{delivery_id}"


def inspect_activity(
    _: WorkflowActivityContext, payload: dict[str, object]
) -> dict[str, object]:
    global _inspection_attempts
    _inspection_attempts += 1
    if _inspection_attempts == 1:
        raise RuntimeError("synthetic transient inspection failure")
    fixture = load_scenario()
    incident = Incident.from_dict(fixture["incident"])
    output = IncidentContextTool(FixtureRepository(fixture), incident).execute(
        {"service": incident.service}
    )
    with DaprClient() as client:
        client.save_state(
            STATE_STORE,
            _inspection_key(str(payload["instance_id"])),
            json.dumps(output, sort_keys=True),
        )
    return output


def execute_activity(
    _: WorkflowActivityContext, payload: dict[str, object]
) -> dict[str, object]:
    fixture = load_scenario()
    incident = Incident.from_dict(fixture["incident"])
    permitted = fixture["runbooks"][incident.service]
    request = ActionRequest(
        action=permitted["action"],
        target=permitted["target"],
        parameters=dict(permitted["parameters"]),
        idempotency_key=incident.delivery_id,
    )
    key = _effect_key(request.idempotency_key)
    with DaprClient() as client:
        existing = client.get_state(STATE_STORE, key).data
        if existing:
            result = json.loads(existing.decode("utf-8"))
            result["replayed"] = True
            return result
        result = {
            "action_id": f"dapr-{incident.incident_id}",
            "idempotency_key": request.idempotency_key,
            "outcome": f"simulated {request.action} on {request.target}",
            "simulated": True,
            "replayed": False,
        }
        client.save_state(STATE_STORE, key, json.dumps(result, sort_keys=True))
        return result


def incident_workflow(ctx: DaprWorkflowContext, payload: dict[str, object]):
    retry = RetryPolicy(
        first_retry_interval=timedelta(milliseconds=200),
        max_number_of_attempts=3,
    )
    inspection = yield ctx.call_activity(
        inspect_activity,
        input=payload,
        retry_policy=retry,
    )
    decision = yield ctx.wait_for_external_event("approval_decision")
    if decision != "approve":
        return {
            "status": "denied",
            "inspection": inspection,
            "action_result": None,
        }
    action_result = yield ctx.call_activity(execute_activity, input=payload)
    return {
        "status": "completed",
        "inspection": inspection,
        "action_result": action_result,
    }


def build_runtime() -> WorkflowRuntime:
    runtime = WorkflowRuntime()
    runtime.register_workflow(incident_workflow, name=WORKFLOW_NAME)
    runtime.register_activity(inspect_activity)
    runtime.register_activity(execute_activity)
    return runtime


def wait_for_inspection(instance_id: str, timeout_seconds: float = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    with DaprClient() as client:
        while time.monotonic() < deadline:
            if client.get_state(STATE_STORE, _inspection_key(instance_id)).data:
                return
            time.sleep(0.25)
    raise TimeoutError("workflow did not reach the approval wait")


def start(instance_id: str) -> None:
    runtime = build_runtime()
    client = DaprWorkflowClient()
    runtime.start()
    try:
        client.schedule_new_workflow(
            workflow=WORKFLOW_NAME,
            input={"instance_id": instance_id},
            instance_id=instance_id,
        )
        client.wait_for_workflow_start(instance_id, timeout_in_seconds=30)
        wait_for_inspection(instance_id)
        print(json.dumps({"instance_id": instance_id, "state": "waiting_for_approval"}))
        while True:
            time.sleep(1)
    finally:
        client.close()
        runtime.shutdown()


def resume(instance_id: str, decision: str, evidence: Path | None) -> None:
    runtime = build_runtime()
    client = DaprWorkflowClient()
    runtime.start()
    try:
        time.sleep(2)
        before = client.get_workflow_state(instance_id, fetch_payloads=True)
        client.raise_workflow_event(instance_id, "approval_decision", data=decision)
        after = client.wait_for_workflow_completion(
            instance_id,
            timeout_in_seconds=30,
            fetch_payloads=True,
        )
        record = {
            "experiment": "03-dapr-agents",
            "probe": "dapr-workflow-crash-restart",
            "instance_id": instance_id,
            "decision": decision,
            "before_restart_resume_status": before.runtime_status.name,
            "final_status": after.runtime_status.name,
            "serialized_output": after.serialized_output,
        }
        rendered = json.dumps(record, indent=2, sort_keys=True)
        if evidence:
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
    finally:
        # Let Dapr remove completion reminders before the workflow worker exits.
        time.sleep(1)
        client.close()
        runtime.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("start", "resume"))
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--decision", choices=("approve", "deny"), default="approve")
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    if args.mode == "start":
        start(args.instance_id)
    else:
        resume(args.instance_id, args.decision, args.evidence)


if __name__ == "__main__":
    main()
