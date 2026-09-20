"""Run-scoped in-memory progress events for the PathWise demo."""

from __future__ import annotations

import asyncio
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Set


PIPELINE_NODES = (
    "profile_parsing",
    "job_search",
    "rag_retrieval",
    "skill_matching",
    "gap_analysis",
    "time_to_ready",
    "training_recommendations",
)


@dataclass
class RunRecord:
    run_id: str
    events: list[Dict[str, Any]] = field(default_factory=list)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    completed: bool = False
    result: Dict[str, Any] | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)


class ProgressEventManager:
    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}
        self._lock = threading.RLock()

    def create_run(self) -> str:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._runs[run_id] = RunRecord(run_id=run_id)
        return run_id

    def has_run(self, run_id: str) -> bool:
        with self._lock:
            return run_id in self._runs

    def publish(
        self,
        run_id: str,
        *,
        node: str,
        label: str,
        status: str,
        message: str,
        data: Dict[str, Any] | None = None,
        error: str | None = None,
        event_type: str = "progress",
    ) -> None:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            return
        event = {
            "run_id": run_id,
            "event_type": event_type,
            "node": node,
            "label": label,
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }
        if error:
            event["error"] = error
        with record.lock:
            record.events.append(event)
            for queue in list(record.subscribers):
                queue.put_nowait(event)

    def complete(self, run_id: str, result: Dict[str, Any]) -> None:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            return
        completed_nodes = set((result.get("node_status") or {}).keys())
        for node in PIPELINE_NODES:
            if node not in completed_nodes and node not in {"job_search_fallback", "rag_fallback", "deterministic_explanation", "tool_execution", "tool_trace"}:
                self.publish(run_id, node=node, label=_label(node), status="skipped", message="Skipped by graph routing.")
        with record.lock:
            record.result = result
            record.completed = True
        is_error = result.get("status") == "error"
        self.publish(
            run_id,
            node="workflow",
            label="Workflow",
            status="failed" if is_error else "completed",
            message="Analysis failed." if is_error else "Analysis complete.",
            data={"status": result.get("status", "completed")},
            error=("Workflow returned an error state." if is_error else None),
            event_type="error" if is_error else "complete",
        )

    def fail(self, run_id: str, message: str) -> None:
        self.publish(run_id, node="workflow", label="Workflow", status="failed", message=message, error=message, event_type="error")
        with self._lock:
            record = self._runs.get(run_id)
        if record:
            with record.lock:
                record.completed = True

    def result(self, run_id: str) -> Dict[str, Any] | None:
        with self._lock:
            record = self._runs.get(run_id)
        return record.result if record else None

    async def subscribe(self, run_id: str) -> AsyncIterator[Dict[str, Any]]:
        with self._lock:
            record = self._runs.get(run_id)
        if record is None:
            return
        queue: asyncio.Queue = asyncio.Queue()
        with record.lock:
            history = list(record.events)
            is_completed = record.completed
            if not is_completed:
                record.subscribers.add(queue)
        try:
            for event in history:
                yield event
            if is_completed:
                return
            while True:
                event = await queue.get()
                yield event
                if event.get("event_type") in {"complete", "error"}:
                    return
        finally:
            with record.lock:
                record.subscribers.discard(queue)


def _label(node: str) -> str:
    return {
        "profile_parsing": "Profile Parsing",
        "job_search": "Job Retrieval",
        "job_search_fallback": "Fallback Job Retrieval",
        "rag_retrieval": "RAG Retrieval",
        "rag_fallback": "RAG Fallback",
        "skill_matching": "Semantic Matching",
        "gap_analysis": "Gap Analysis",
        "opportunity_simulation": "Opportunity Analysis",
        "time_to_ready": "Readiness + AI Reasoning",
        "gemini_tool_agent": "AI Tool Selection",
        "tool_execution": "Tool Execution",
        "tool_trace": "Tool Results",
        "gemini_reasoning": "AI Reasoning",
        "deterministic_explanation": "Deterministic Explanation",
        "training_recommendations": "Training Plan",
        "report": "Report",
        "workflow": "Workflow",
    }.get(node, node.replace("_", " ").title())


def format_sse(event: Dict[str, Any]) -> str:
    event_type = event.get("event_type", "progress")
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


progress_manager = ProgressEventManager()
