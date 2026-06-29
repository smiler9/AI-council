from __future__ import annotations

import json
from pathlib import Path

from .database import PROJECT_ROOT
from .council import SAFETY_BOUNDARY


DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def build_markdown_report(
    meeting: dict,
    outputs: list[dict],
    messages: list[dict] | None = None,
) -> str:
    ticker = meeting.get("ticker") or "N/A"
    context_files = meeting.get("context_files", [])
    trade_signal = meeting.get("trade_signal") or {}
    debate_messages = messages or []
    structured_decision = meeting.get("structured_decision", {})
    trade_review = json.dumps(meeting["trade_review"], indent=2, sort_keys=True)
    decision_json = json.dumps(structured_decision, indent=2, sort_keys=True)
    lines = [
        f"# AI Council Report: {meeting['topic']}",
        "",
        "## Meeting",
        "",
        f"- Meeting ID: `{meeting['id']}`",
        f"- Ticker: `{ticker}`",
        f"- Meeting Mode: `{meeting.get('mode', 'quick_review')}`",
        f"- Status: `{meeting['status']}`",
        f"- Created: `{meeting['created_at']}`",
        f"- Updated: `{meeting['updated_at']}`",
        "",
        "## Meeting Mode",
        "",
        f"`{meeting.get('mode', 'quick_review')}`",
        "",
        "## Trade Signal Context",
        "",
    ]
    if trade_signal:
        lines.extend(
            [
                "This external signal was reviewed as read-only context. It is not an order.",
                "",
                "```json",
                json.dumps(trade_signal, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    else:
        lines.extend(["No external trade signal context.", ""])
    lines.extend(
        [
            "## Attached Context Files",
            "",
        ]
    )
    if context_files:
        for file in context_files:
            lines.append(
                f"- `{file['original_filename']}` ({file['file_type']}, {file['status']}, {file['file_size']} bytes)"
            )
    else:
        lines.append("No attached context files.")
    lines.extend(
        [
            "",
            "## File Summaries",
            "",
        ]
    )
    if context_files:
        for file in context_files:
            lines.extend(
                [
                    f"### {file['original_filename']}",
                    "",
                    file["summary"],
                    "",
                ]
            )
    else:
        lines.extend(["No file summaries available.", ""])
    lines.extend(
        [
            "## Debate Rounds",
            "",
        ]
    )
    if debate_messages:
        for round_name, title in [
            ("initial_opinion", "Round 1: initial_opinion"),
            ("rebuttal", "Round 2: rebuttal"),
            ("revision", "Round 3: revision"),
            ("chairman_summary", "Round 4: chairman_summary"),
            ("structured_decision", "Round 5: structured_decision"),
        ]:
            round_messages = [
                message for message in debate_messages if message["round"] == round_name
            ]
            lines.extend([f"### {title}", ""])
            if round_messages:
                for message in round_messages:
                    lines.extend(
                        [
                            f"#### {message['agent_name']}",
                            "",
                            f"- Type: `{message['message_type']}`",
                            f"- Confidence: `{message['confidence']:.2f}`",
                            f"- Risk Level: `{message['risk_level']}`",
                            "",
                            message["content"],
                            "",
                        ]
                    )
            else:
                lines.extend(["No messages recorded for this round.", ""])
    else:
        lines.extend(["No debate rounds recorded.", ""])
    lines.extend(
        [
            "## Agent Initial Opinions",
            "",
        ]
    )
    _append_round_messages(lines, debate_messages, "initial_opinion")
    lines.extend(["## Rebuttals", ""])
    _append_round_messages(lines, debate_messages, "rebuttal")
    lines.extend(["## Revised Notes", ""])
    _append_round_messages(lines, debate_messages, "revision")
    lines.extend(
        [
            "## Agent Outputs",
            "",
        ]
    )
    for output in outputs:
        lines.extend(
            [
                f"### {output['agent_name']}",
                "",
                f"- Stage: `{output['stage']}`",
                f"- Stance: `{output['stance']}`",
                f"- Confidence: `{output['confidence']:.2f}`",
                f"- Provider: `{output.get('provider_name', 'mock')}`",
                "",
                output["content"],
                "",
            ]
        )
    lines.extend(
        [
            "## Context-aware Agent Notes",
            "",
        ]
    )
    context_outputs = [
        output
        for output in outputs
        if output.get("structured_response", {}).get("raw", {}).get("context_file_count", 0)
    ]
    if context_outputs:
        for output in context_outputs:
            raw = output.get("structured_response", {}).get("raw", {})
            filenames = ", ".join(raw.get("context_filenames", [])) or "attached files"
            lines.append(
                f"- {output['agent_name']} referenced {raw.get('context_file_count', 0)} file(s): {filenames}."
            )
    else:
        lines.append("No file-aware notes were generated for this meeting.")
    lines.append("")
    lines.extend(
        [
            "## Structured Decision",
            "",
            "```json",
            decision_json,
            "```",
            "",
            "## Risk Flags",
            "",
        ]
    )
    risk_flags = structured_decision.get("risk_flags", [])
    if risk_flags:
        lines.extend(f"- `{flag}`" for flag in risk_flags)
    else:
        lines.append("No risk flags recorded.")
    lines.extend(["", "## Required Follow-up", ""])
    follow_up = structured_decision.get("required_follow_up", [])
    if follow_up:
        lines.extend(f"- {item}" for item in follow_up)
    else:
        lines.append("No follow-up recorded.")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            SAFETY_BOUNDARY,
            "",
        ]
    )
    lines.extend(
        [
            "## Future Trade Review Metadata",
            "",
            "This metadata is for future review integration only. Phase 1 does not execute trades.",
            "",
            "```json",
            trade_review,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _append_round_messages(lines: list[str], messages: list[dict], round_name: str) -> None:
    selected = [message for message in messages if message["round"] == round_name]
    if not selected:
        lines.extend(["No messages recorded.", ""])
        return
    for message in selected:
        lines.extend(
            [
                f"### {message['agent_name']}",
                "",
                f"- Risk Level: `{message['risk_level']}`",
                f"- Confidence: `{message['confidence']:.2f}`",
                "",
                message["content"],
                "",
            ]
        )


def write_markdown_report(
    meeting: dict,
    outputs: list[dict],
    report_dir: str | Path | None = None,
    messages: list[dict] | None = None,
) -> tuple[Path, str]:
    directory = Path(report_dir or DEFAULT_REPORT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown_report(meeting, outputs, messages=messages)
    report_path = directory / f"meeting_{meeting['id']}.md"
    report_path.write_text(markdown, encoding="utf-8")
    return report_path, markdown
