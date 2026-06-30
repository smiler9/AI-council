from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
KOREAN_SAFETY_BOUNDARY = (
    "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. "
    "이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다."
)


def test_frontend_contains_korean_localization_strings():
    app_source = (PROJECT_ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")

    for phrase in [
        "대시보드",
        "자율 트레이더 검토",
        "시장 데이터 상태",
        "새 회의 만들기",
        "거래 신호 검토",
        "웹훅 수신기",
        "텔레그램으로 보내기",
        "구조화된 판단",
        "주문 실행 허용 여부",
        "안전 경계",
    ]:
        assert phrase in app_source


def test_readme_contains_korean_safety_boundary_and_phase_summary():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert KOREAN_SAFETY_BOUNDARY in readme
    assert "Phase 10: 한글 중심 UI/문서/리포트 정리" in readme
    assert "실제 브로커 API 연결" in readme
    assert "order_execution_allowed" in readme


def test_examples_docs_are_korean_first():
    external_bot = (
        PROJECT_ROOT / "examples" / "external_bot" / "README.md"
    ).read_text(encoding="utf-8")
    integration = (
        PROJECT_ROOT / "examples" / "integration" / "README.md"
    ).read_text(encoding="utf-8")
    sample_results = (
        PROJECT_ROOT / "examples" / "integration" / "sample_results_example.md"
    ).read_text(encoding="utf-8")

    assert "외부 봇 샘플 클라이언트" in external_bot
    assert KOREAN_SAFETY_BOUNDARY in external_bot
    assert "Webhook 통합 Smoke Test" in integration
    assert KOREAN_SAFETY_BOUNDARY in integration
    assert "결과 예시" in sample_results
    assert "order_execution_allowed" in sample_results
