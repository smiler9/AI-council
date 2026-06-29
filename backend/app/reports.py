from __future__ import annotations

import json
from pathlib import Path

from .database import PROJECT_ROOT


DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def build_markdown_report(meeting: dict, outputs: list[dict]) -> str:
    ticker = meeting.get("ticker") or "N/A"
    context_files = meeting.get("context_files", [])
    trade_review = json.dumps(meeting["trade_review"], indent=2, sort_keys=True)
    lines = [
        f"# AI Council Report: {meeting['topic']}",
        "",
        "## Meeting",
        "",
        f"- Meeting ID: `{meeting['id']}`",
        f"- Ticker: `{ticker}`",
        f"- Status: `{meeting['status']}`",
        f"- Created: `{meeting['created_at']}`",
        f"- Updated: `{meeting['updated_at']}`",
        "",
        "## Attached Context Files",
        "",
    ]
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


def write_markdown_report(
    meeting: dict,
    outputs: list[dict],
    report_dir: str | Path | None = None,
) -> tuple[Path, str]:
    directory = Path(report_dir or DEFAULT_REPORT_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    markdown = build_markdown_report(meeting, outputs)
    report_path = directory / f"meeting_{meeting['id']}.md"
    report_path.write_text(markdown, encoding="utf-8")
    return report_path, markdown
