from __future__ import annotations

import json
from pathlib import Path

from .database import PROJECT_ROOT


DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def build_markdown_report(meeting: dict, outputs: list[dict]) -> str:
    ticker = meeting.get("ticker") or "N/A"
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
        "## Agent Outputs",
        "",
    ]
    for output in outputs:
        lines.extend(
            [
                f"### {output['agent_name']}",
                "",
                f"- Stage: `{output['stage']}`",
                f"- Stance: `{output['stance']}`",
                f"- Confidence: `{output['confidence']:.2f}`",
                "",
                output["content"],
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

