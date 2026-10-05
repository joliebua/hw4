"""Offline checks for the append-only audit trail — no API calls.

A scripted FunctionModel stands in for the real model and drives a real agent
loop (search → validator retry → final answer), so every kind of step gets
logged. Writes to a temporary trail file, never output/audit_trail.json.

Run from backend/ with .venv active:

    python tests/test_audit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Run from backend/:  python tests/<this file>.py   (the app modules live one folder up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import tempfile

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

import agent
from models import AuditEvent, PageContext

agent.AUDIT_FILE = Path(tempfile.mkdtemp()) / "audit_trail.json"


def scripted_model(messages, info: AgentInfo) -> ModelResponse:
    """1st call: search. 2nd: answer with a made-up price (validator rejects).
    3rd: answer correctly with the database price."""
    final = info.output_tools[0].name
    calls = sum(1 for m in messages if isinstance(m, ModelResponse))
    if calls == 0:
        return ModelResponse(parts=[ToolCallPart("check_stock", {"product_id": "yale-mom-hoodie", "size": "XXL"})])
    if calls == 1:
        return ModelResponse(parts=[ToolCallPart(final, {"message": "Only $19 today, 99 left in XXL!", "product_ids": []})])
    return ModelResponse(
        parts=[ToolCallPart(final, {"message": "The Yale Mom Hoodie is $68, with 2 on hand in XXL.", "product_ids": ["yale-mom-hoodie"]})]
    )


def run_turn(message: str = "is the mom hoodie in XXL?"):
    with agent.get_agent().override(model=FunctionModel(scripted_model)):
        return asyncio.run(
            agent.chat(message, None, None, PageContext(path="/products/yale-mom-hoodie", product_id="yale-mom-hoodie"))
        )


def lines() -> list[dict]:
    return [json.loads(line) for line in agent.AUDIT_FILE.read_text().splitlines() if line.strip()]


def test_every_loop_step_is_logged():
    reply = run_turn()
    assert "$68" in reply.reply
    entries = lines()
    events = [e["event"] for e in entries]
    assert events[0] == AuditEvent.RUN_START and events[-1] == AuditEvent.RUN_END
    assert len({e["run_id"] for e in entries}) == 1

    # The tool call, its result, the validator's retry, and the final answer are all there.
    calls = [c for e in entries for c in e["tool_calls"]]
    assert any(c["tool_name"] == "check_stock" and '"size":"XXL"' in c["args_summary"] for c in calls)
    assert any(c["tool_name"] == "check_stock" and "2 on hand" in c["result_summary"] for c in calls)
    retry = [e for e in entries if e["stop_reason"] == "retry"]
    assert retry and not retry[0]["tool_calls"][0]["ok"] and "$19" in retry[0]["tool_calls"][0]["result_summary"]

    start, end = entries[0], entries[-1]
    assert start["shopper"] == "guest" and start["page"] == "product:yale-mom-hoodie"
    assert end["stop_reason"] == "completed" and "$68" in end["reply_summary"]
    assert [e["iteration"] for e in entries] == list(range(len(entries)))


def test_trail_is_append_only_across_runs():
    before = agent.AUDIT_FILE.read_text()
    run_turn("second run")
    after = agent.AUDIT_FILE.read_text()
    assert after.startswith(before) and len(after) > len(before), "earlier lines must be kept untouched"
    assert len({e["run_id"] for e in lines()}) == 2


def test_card_numbers_never_reach_the_trail():
    run_turn("my card is 4111 1111 1111 1111, is it in XXL?")
    text = agent.AUDIT_FILE.read_text()
    assert "4111" not in text and "[card number removed]" in text


def test_summaries_are_short():
    long = agent.summarise({"x": "y" * 5000})
    assert len(long) <= agent.SUMMARY_CHARS and long.endswith("…")


if __name__ == "__main__":
    tests = [(n, f) for n, f in globals().items() if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print(f"ok  {name}")
    print(f"\n{len(tests)} passed (trail written to a temporary file)")
