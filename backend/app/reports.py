from __future__ import annotations

import json
from pathlib import Path

from .database import PROJECT_ROOT
from .council import KOREAN_SAFETY_BOUNDARY, SAFETY_BOUNDARY


DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


def build_markdown_report(
    meeting: dict,
    outputs: list[dict],
    messages: list[dict] | None = None,
) -> str:
    ticker = meeting.get("ticker") or "N/A"
    context_files = meeting.get("context_files", [])
    trade_signal = meeting.get("trade_signal") or {}
    auto_research_metadata = trade_signal.get("auto_research_metadata") or {}
    auto_research_context = trade_signal.get("risk_context") or {}
    debate_messages = messages or []
    structured_decision = meeting.get("structured_decision", {})
    trade_review = json.dumps(meeting["trade_review"], indent=2, sort_keys=True)
    decision_json = json.dumps(structured_decision, indent=2, sort_keys=True)
    lines = [
        f"# AI Council 회의 보고서: {meeting['topic']}",
        "",
        "## 회의 정보 (Meeting)",
        "",
        f"- 회의 ID: `{meeting['id']}`",
        f"- 종목명: `{ticker}`",
        f"- 회의 모드: `{meeting.get('mode', 'quick_review')}`",
        f"- 상태: `{meeting['status']}`",
        f"- 생성 시각: `{meeting['created_at']}`",
        f"- 수정 시각: `{meeting['updated_at']}`",
        "",
        "## 회의 모드 (Meeting Mode)",
        "",
        f"`{meeting.get('mode', 'quick_review')}`",
        "",
        "## 거래 신호 컨텍스트 (Trade Signal Context)",
        "",
    ]
    if trade_signal.get("source") == "ticker_only_auto_research" or auto_research_metadata:
        lines.extend(
            [
                "## 종목 자동 분석 요청",
                "",
                f"- 티커: `{trade_signal.get('ticker', ticker)}`",
                f"- 리뷰 모드: `{auto_research_metadata.get('review_mode') or auto_research_context.get('review_mode', 'general_review')}`",
                f"- 타임프레임: `{auto_research_metadata.get('timeframe') or trade_signal.get('timeframe') or '1d'}`",
                f"- 요청 출처: `{trade_signal.get('source', 'ticker_only_auto_research')}`",
                "",
                "## 자동 생성된 분석 payload",
                "",
                "```json",
                json.dumps(trade_signal, indent=2, sort_keys=True),
                "```",
                "",
                "## 사용된 데이터 provider",
                "",
                f"`{auto_research_metadata.get('market_data_provider') or auto_research_context.get('market_data_provider') or auto_research_context.get('data_source') or 'mock_market_data'}`",
                "",
                "## 데이터 품질",
                "",
                f"`{auto_research_context.get('data_quality', 'limited')}`",
                "",
            ]
        )
    if trade_signal:
        lines.extend(
            [
                "이 외부 신호는 읽기 전용 검토 문맥으로만 사용되었습니다. 주문이 아닙니다.",
                "",
                "```json",
                json.dumps(trade_signal, indent=2, sort_keys=True),
                "```",
                "",
            ]
        )
    else:
        lines.extend(["외부 거래 신호 컨텍스트가 없습니다.", ""])
    lines.extend(
        [
            "## 첨부된 참고 파일 (Attached Context Files)",
            "",
        ]
    )
    if context_files:
        for file in context_files:
            lines.append(
                f"- `{file['original_filename']}` ({file['file_type']}, {file['status']}, {file['file_size']} bytes)"
            )
    else:
        lines.append("첨부된 참고 파일이 없습니다.")
    lines.extend(
        [
            "",
            "## 파일 요약 (File Summaries)",
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
        lines.extend(["사용 가능한 파일 요약이 없습니다.", ""])
    lines.extend(
        [
            "## 토론 라운드 (Debate Rounds)",
            "",
        ]
    )
    if debate_messages:
        for round_name, title in [
            ("initial_opinion", "1라운드: 1차 의견 (initial_opinion)"),
            ("rebuttal", "2라운드: 반박 (rebuttal)"),
            ("revision", "3라운드: 수정 의견 (revision)"),
            ("chairman_summary", "4라운드: 의장 요약 (chairman_summary)"),
            ("structured_decision", "5라운드: 구조화된 판단 (structured_decision)"),
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
                            f"- 유형: `{message['message_type']}`",
                            f"- 신뢰도: `{message['confidence']:.2f}`",
                            f"- 리스크 수준: `{message['risk_level']}`",
                            "",
                            message["content"],
                            "",
                        ]
                    )
            else:
                lines.extend(["이 라운드에 기록된 메시지가 없습니다.", ""])
    else:
        lines.extend(["기록된 토론 라운드가 없습니다.", ""])
    lines.extend(
        [
            "## 에이전트 1차 의견 (Agent Initial Opinions)",
            "",
        ]
    )
    _append_round_messages(lines, debate_messages, "initial_opinion")
    lines.extend(["## 반박 의견 (Rebuttals)", ""])
    _append_round_messages(lines, debate_messages, "rebuttal")
    lines.extend(["## 수정 의견 (Revised Notes)", ""])
    _append_round_messages(lines, debate_messages, "revision")
    lines.extend(
        [
            "## 에이전트 출력 (Agent Outputs)",
            "",
        ]
    )
    for output in outputs:
        lines.extend(
            [
                f"### {output['agent_name']}",
                "",
                f"- 단계: `{output['stage']}`",
                f"- 관점: `{output['stance']}`",
                f"- 신뢰도: `{output['confidence']:.2f}`",
                f"- Provider: `{output.get('provider_name', 'mock')}`",
                "",
                output["content"],
                "",
            ]
        )
    lines.extend(
        [
            "## 컨텍스트 기반 에이전트 메모 (Context-aware Agent Notes)",
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
                f"- {output['agent_name']}가 {raw.get('context_file_count', 0)}개 파일을 참고했습니다: {filenames}."
            )
    else:
        lines.append("이 회의에서는 파일 기반 메모가 생성되지 않았습니다.")
    lines.append("")
    lines.extend(
        [
            "## 구조화된 판단 (Structured Decision)",
            "",
            "```json",
            decision_json,
            "```",
            "",
            "## 리스크 플래그 (Risk Flags)",
            "",
        ]
    )
    risk_flags = structured_decision.get("risk_flags", [])
    if risk_flags:
        lines.extend(f"- `{flag}`" for flag in risk_flags)
    else:
        lines.append("기록된 리스크 플래그가 없습니다.")
    lines.extend(["", "## 추가 확인 필요사항 (Required Follow-up)", ""])
    follow_up = structured_decision.get("required_follow_up", [])
    if follow_up:
        lines.extend(f"- {item}" for item in follow_up)
    else:
        lines.append("기록된 추가 확인 사항이 없습니다.")
    lines.extend(
        [
            "",
            "## 안전 경계 (Safety Boundary)",
            "",
            KOREAN_SAFETY_BOUNDARY,
            "",
            SAFETY_BOUNDARY,
            "",
        ]
    )
    lines.extend(
        [
            "## 향후 거래 검토 메타데이터 (Future Trade Review Metadata)",
            "",
            "이 메타데이터는 향후 검토 연동을 위한 구조입니다. AI Council은 거래를 실행하지 않습니다.",
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
        lines.extend(["기록된 메시지가 없습니다.", ""])
        return
    for message in selected:
        lines.extend(
            [
                f"### {message['agent_name']}",
                "",
                f"- 리스크 수준: `{message['risk_level']}`",
                f"- 신뢰도: `{message['confidence']:.2f}`",
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
