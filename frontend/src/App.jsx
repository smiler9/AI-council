import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  FileText,
  ListChecks,
  Play,
  Plus,
  RefreshCw,
  Scale,
  Shield,
  Send,
  Trash2,
  Upload
} from "lucide-react";
import { api } from "./api";

const SAFETY_BOUNDARY =
  "AI Council does not execute trades or connect to broker APIs. This output is for review, risk analysis, and decision support only.";
const KOREAN_SAFETY_BOUNDARY =
  "AI Council은 거래를 실행하거나 브로커 API에 연결하지 않습니다. 이 결과는 검토, 리스크 분석, 의사결정 보조 목적으로만 사용됩니다.";

const DECISION_LABELS = {
  ALLOW: "검토상 허용",
  HOLD: "보류",
  BLOCK: "차단",
  NEED_MORE_DATA: "추가 데이터 필요"
};

const RISK_LEVEL_LABELS = {
  low: "낮음",
  medium: "보통",
  high: "높음",
  critical: "매우 높음"
};

const DATA_QUALITY_LABELS = {
  limited: "제한적",
  sufficient: "충분",
  poor: "부족",
  unknown: "알 수 없음",
  moderate: "보통",
  failed: "실패",
  unavailable: "사용 불가"
};

const AGENT_LABELS = {
  "Financial Statement Agent": "재무제표 분석 에이전트",
  "News Catalyst Agent": "뉴스 촉매 분석 에이전트",
  "Technical Momentum Agent": "기술적 모멘텀 에이전트",
  "Risk Manager Agent": "리스크 관리자 에이전트",
  "Pump & Dump Risk Agent": "펌프앤덤프 위험 감시 에이전트",
  "Skeptic Agent": "비판 검토 에이전트",
  "Chairman Agent": "의장 에이전트"
};

const MODE_LABELS = {
  quick_review: "빠른 검토",
  deep_debate: "심층 토론",
  skeptic_review: "비판 중심 검토",
  risk_gate_review: "리스크 게이트 검토",
  action_plan: "실행 계획 수립"
};

const ROUND_LABELS = {
  initial_opinion: "1라운드: 1차 의견",
  rebuttal: "2라운드: 반박",
  revision: "3라운드: 수정 의견",
  chairman_summary: "4라운드: 의장 요약",
  structured_decision: "5라운드: 구조화된 판단"
};

const MESSAGE_TYPE_LABELS = {
  analysis: "분석",
  rebuttal: "반박",
  revision: "수정",
  summary: "요약",
  decision: "판단"
};

function statusLabel(status) {
  if (status === "completed") return "완료";
  if (status === "failed") return "실패";
  if (status === "running") return "실행 중";
  return "초안";
}

function stageIcon(stage) {
  if (stage === "summary") return <Scale size={18} aria-hidden="true" />;
  if (stage === "rebuttal") return <AlertTriangle size={18} aria-hidden="true" />;
  return <Brain size={18} aria-hidden="true" />;
}

function modeLabel(mode) {
  const value = mode || "quick_review";
  return `${MODE_LABELS[value] || value.replaceAll("_", " ")} (${value})`;
}

function decisionLabel(value) {
  if (!value) return "대기 중";
  return `${DECISION_LABELS[value] || value} (${value})`;
}

function riskLevelLabel(value) {
  if (!value) return "미평가";
  return `${RISK_LEVEL_LABELS[value] || value} (${value})`;
}

function dataQualityLabel(value) {
  if (!value) return "알 수 없음";
  return `${DATA_QUALITY_LABELS[value] || value} (${value})`;
}

function agentLabel(name) {
  return AGENT_LABELS[name] ? `${AGENT_LABELS[name]} (${name})` : name;
}

function messageTypeLabel(value) {
  return MESSAGE_TYPE_LABELS[value] ? `${MESSAGE_TYPE_LABELS[value]} (${value})` : value;
}

function booleanKo(value) {
  return value ? "예 (true)" : "아니오 (false)";
}

export default function App() {
  const [agents, setAgents] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [tradeReviews, setTradeReviews] = useState([]);
  const [health, setHealth] = useState(null);
  const [marketDataStatus, setMarketDataStatus] = useState(null);
  const [webhookStatus, setWebhookStatus] = useState(null);
  const [webhookEvents, setWebhookEvents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [topic, setTopic] = useState("");
  const [ticker, setTicker] = useState("");
  const [mode, setMode] = useState("quick_review");
  const [tradeReviewForm, setTradeReviewForm] = useState({
    ticker: "",
    strategy_signal: "breakout",
    side: "watch_only",
    price: "",
    volume: "",
    timeframe: "1m",
    spread_pct: "",
    premarket: false,
    rsi: "",
    vwap_distance: "",
    notes: "",
    news_headlines: ""
  });
  const [tickerReviewForm, setTickerReviewForm] = useState({
    ticker: "",
    review_mode: "penny_stock_risk",
    timeframe: "1d",
    notes: ""
  });
  const [autonomousReviewForm, setAutonomousReviewForm] = useState({
    universe: "mock_penny_stocks",
    review_mode: "penny_stock_risk",
    max_candidates: 5,
    timeframe: "1d",
    notes: "자율 후보 발굴 및 검토"
  });
  const [marketDataTicker, setMarketDataTicker] = useState("TESTA");
  const [marketDataResult, setMarketDataResult] = useState(null);
  const [tradeReviewResult, setTradeReviewResult] = useState(null);
  const [tickerReviewResult, setTickerReviewResult] = useState(null);
  const [autonomousReviewResult, setAutonomousReviewResult] = useState(null);
  const [tradeReviewTelegramResult, setTradeReviewTelegramResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tradeReviewLoading, setTradeReviewLoading] = useState(false);
  const [tickerReviewLoading, setTickerReviewLoading] = useState(false);
  const [autonomousReviewLoading, setAutonomousReviewLoading] = useState(false);
  const [marketDataLoading, setMarketDataLoading] = useState(false);
  const [fileLoading, setFileLoading] = useState(false);
  const [telegramLoading, setTelegramLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [telegramResult, setTelegramResult] = useState(null);
  const [error, setError] = useState("");

  const selectedMeeting = detail?.meeting;
  const contextFiles = detail?.files || [];
  const messages = detail?.messages || [];
  const structuredDecision =
    detail?.structured_decision || selectedMeeting?.structured_decision || {};

  const groupedOutputs = useMemo(() => {
    const groups = { analysis: [], rebuttal: [], summary: [] };
    for (const output of detail?.outputs || []) {
      groups[output.stage] = [...(groups[output.stage] || []), output];
    }
    return groups;
  }, [detail]);

  async function loadMeetings(nextSelectedId = selectedId) {
    const meetingList = await api.getMeetings();
    setMeetings(meetingList);
    const fallbackId = meetingList[0]?.id || null;
    const idToLoad = nextSelectedId || fallbackId;
    setSelectedId(idToLoad);
    if (idToLoad) {
      setDetail(await api.getMeeting(idToLoad));
    } else {
      setDetail(null);
    }
  }

  async function loadInitialData() {
    setError("");
    try {
      const [healthStatus, marketStatus, agentList, telegram, reviewList, hooks, events] = await Promise.all([
        api.getHealth(),
        api.getMarketDataStatus(),
        api.getAgents(),
        api.getTelegramStatus(),
        api.getTradeReviews(),
        api.getWebhookStatus(),
        api.getWebhookEvents()
      ]);
      setHealth(healthStatus);
      setMarketDataStatus(marketStatus);
      setAgents(agentList);
      setTelegramStatus(telegram);
      setTradeReviews(reviewList);
      setWebhookStatus(hooks);
      setWebhookEvents(events);
      await loadMeetings();
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadInitialData();
  }, []);

  async function handleCreate(event) {
    event.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    try {
      const meeting = await api.createMeeting({
        topic: topic.trim(),
        ticker: ticker.trim() || null,
        mode
      });
      setTopic("");
      setTicker("");
      setMode("quick_review");
      await loadMeetings(meeting.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function updateTradeReviewField(field, value) {
    setTradeReviewForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function updateTickerReviewField(field, value) {
    setTickerReviewForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function updateAutonomousReviewField(field, value) {
    setAutonomousReviewForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function buildTradeReviewPayload() {
    const numberOrNull = (value) => {
      if (value === "" || value === null || value === undefined) return null;
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : null;
    };
    const technicalIndicators = {};
    const rsi = numberOrNull(tradeReviewForm.rsi);
    const vwapDistance = numberOrNull(tradeReviewForm.vwap_distance);
    if (rsi !== null) technicalIndicators.rsi = rsi;
    if (vwapDistance !== null) technicalIndicators.vwap_distance = vwapDistance;
    const riskContext = {
      premarket: Boolean(tradeReviewForm.premarket)
    };
    const spreadPct = numberOrNull(tradeReviewForm.spread_pct);
    if (spreadPct !== null) riskContext.spread_pct = spreadPct;
    return {
      ticker: tradeReviewForm.ticker.trim(),
      strategy_signal: tradeReviewForm.strategy_signal.trim(),
      side: tradeReviewForm.side.trim() || "review_only",
      price: numberOrNull(tradeReviewForm.price),
      volume: numberOrNull(tradeReviewForm.volume),
      timeframe: tradeReviewForm.timeframe.trim() || null,
      source: "external_bot",
      notes: tradeReviewForm.notes.trim() || null,
      technical_indicators: technicalIndicators,
      news_headlines: tradeReviewForm.news_headlines
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
      risk_context: riskContext
    };
  }

  async function handleTradeReviewSubmit(event) {
    event.preventDefault();
    if (!tradeReviewForm.ticker.trim() || !tradeReviewForm.strategy_signal.trim()) return;
    setTradeReviewLoading(true);
    setTradeReviewTelegramResult(null);
    setError("");
    try {
      const result = await api.createTradeReview(buildTradeReviewPayload());
      setTradeReviewResult(result);
      setTradeReviews(await api.getTradeReviews());
      if (result.meeting?.id) {
        await loadMeetings(result.meeting.id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setTradeReviewLoading(false);
    }
  }

  async function handleTickerReviewSubmit(event) {
    event.preventDefault();
    if (!tickerReviewForm.ticker.trim()) return;
    setTickerReviewLoading(true);
    setError("");
    try {
      const result = await api.createTickerReview({
        ticker: tickerReviewForm.ticker.trim(),
        review_mode: tickerReviewForm.review_mode,
        timeframe: tickerReviewForm.timeframe.trim() || "1d",
        notes: tickerReviewForm.notes.trim() || null
      });
      setTickerReviewResult(result);
      setTradeReviews(await api.getTradeReviews());
      if (result.meeting?.id) {
        await loadMeetings(result.meeting.id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setTickerReviewLoading(false);
    }
  }

  async function handleAutonomousReviewSubmit(event) {
    event.preventDefault();
    setAutonomousReviewLoading(true);
    setError("");
    try {
      const result = await api.createAutonomousReview({
        universe: autonomousReviewForm.universe,
        review_mode: autonomousReviewForm.review_mode,
        max_candidates: Number(autonomousReviewForm.max_candidates) || 5,
        timeframe: autonomousReviewForm.timeframe.trim() || "1d",
        notes: autonomousReviewForm.notes.trim() || null
      });
      setAutonomousReviewResult(result);
      setTradeReviews(await api.getTradeReviews());
      const firstMeetingId = result.results?.[0]?.linked_meeting_id;
      if (firstMeetingId) {
        await loadMeetings(firstMeetingId);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setAutonomousReviewLoading(false);
    }
  }

  async function handleMarketDataLookup(kind) {
    const tickerValue = marketDataTicker.trim();
    if (!tickerValue) return;
    setMarketDataLoading(true);
    setError("");
    try {
      const requestMap = {
        quote: api.getMarketDataQuote,
        snapshot: api.getMarketDataSnapshot,
        news: api.getMarketDataNews,
        filings: api.getMarketDataFilings
      };
      const payload = await requestMap[kind](tickerValue);
      setMarketDataResult({ kind, payload });
      setMarketDataStatus(await api.getMarketDataStatus());
    } catch (err) {
      setError(err.message);
    } finally {
      setMarketDataLoading(false);
    }
  }

  async function handleSendTradeReviewTelegram() {
    const reviewId = tradeReviewResult?.trade_review?.id;
    if (!reviewId) return;
    setTradeReviewLoading(true);
    setTradeReviewTelegramResult(null);
    setError("");
    try {
      const result = await api.sendTradeReviewTelegram(reviewId);
      setTradeReviewTelegramResult(result);
      await refreshTelegramStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setTradeReviewLoading(false);
    }
  }

  async function handleSelect(meetingId) {
    setSelectedId(meetingId);
    setError("");
    try {
      setDetail(await api.getMeeting(meetingId));
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRun() {
    if (!selectedId) return;
    setLoading(true);
    setError("");
    try {
      const payload = await api.runMeeting(selectedId);
      setDetail({
        meeting: payload.meeting,
        outputs: payload.outputs,
        messages: payload.messages || [],
        structured_decision: payload.structured_decision || {},
        files: payload.files || contextFiles,
        report: payload.report
      });
      await loadMeetings(selectedId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUploadFile(event) {
    event.preventDefault();
    if (!selectedId || !selectedFile) return;
    setFileLoading(true);
    setError("");
    try {
      await api.uploadMeetingFile(selectedId, selectedFile);
      setSelectedFile(null);
      event.target.reset();
      setDetail(await api.getMeeting(selectedId));
    } catch (err) {
      setError(err.message);
    } finally {
      setFileLoading(false);
    }
  }

  async function handleDeleteFile(fileId) {
    if (!selectedId) return;
    setFileLoading(true);
    setError("");
    try {
      await api.deleteFile(fileId);
      setDetail(await api.getMeeting(selectedId));
    } catch (err) {
      setError(err.message);
    } finally {
      setFileLoading(false);
    }
  }

  async function refreshTelegramStatus() {
    try {
      setTelegramStatus(await api.getTelegramStatus());
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshWebhookData() {
    try {
      const [hooks, events, reviewList] = await Promise.all([
        api.getWebhookStatus(),
        api.getWebhookEvents(),
        api.getTradeReviews()
      ]);
      setWebhookStatus(hooks);
      setWebhookEvents(events);
      setTradeReviews(reviewList);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSendTelegram() {
    if (!selectedId) return;
    setTelegramLoading(true);
    setTelegramResult(null);
    setError("");
    try {
      const result = await api.sendTelegram(selectedId);
      setTelegramResult(result);
      await refreshTelegramStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setTelegramLoading(false);
    }
  }

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <Brain size={24} aria-hidden="true" />
          </div>
          <div>
            <h1>AI Council</h1>
            <p>검토와 리스크 분석 회의실</p>
          </div>
        </div>

        <nav className="sectionNav" aria-label="AI Council 주요 섹션">
          <a href="#dashboard">대시보드</a>
          <a href="#meetings">회의</a>
          <a href="#market-data">시장 데이터 상태</a>
          <a href="#autonomous-review">자율 트레이더 검토</a>
          <a href="#ticker-review">종목 자동 분석</a>
          <a href="#trade-review">거래 신호 검토</a>
          <a href="#webhooks">웹훅</a>
          <a href="#telegram">텔레그램</a>
          <a href="#settings-guide">설정/가이드</a>
        </nav>

        <form className="createForm" onSubmit={handleCreate}>
          <h2>새 회의 만들기</h2>
          <label>
            <span>분석 주제</span>
            <textarea
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="예: TEST 돌파 신호의 리스크를 검토해줘"
              rows={4}
            />
          </label>
          <label>
            <span>종목명</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="선택 입력"
              maxLength={16}
            />
          </label>
          <label>
            <span>회의 모드</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="quick_review">빠른 검토 (quick_review)</option>
              <option value="deep_debate">심층 토론 (deep_debate)</option>
              <option value="skeptic_review">비판 중심 검토 (skeptic_review)</option>
              <option value="risk_gate_review">리스크 게이트 검토 (risk_gate_review)</option>
              <option value="action_plan">실행 계획 수립 (action_plan)</option>
            </select>
          </label>
          <button className="primaryButton" type="submit" disabled={loading || !topic.trim()}>
            <Plus size={18} aria-hidden="true" />
            회의 만들기
          </button>
        </form>

        <div className="sidebarHeader">
          <span>회의 목록</span>
          <button
            className="iconButton"
            type="button"
            title="회의 목록 새로고침"
            onClick={() => loadMeetings()}
          >
            <RefreshCw size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="meetingList">
          {meetings.map((meeting) => (
            <button
              className={`meetingItem ${selectedId === meeting.id ? "active" : ""}`}
              key={meeting.id}
              type="button"
              onClick={() => handleSelect(meeting.id)}
            >
              <span className="meetingTitle">{meeting.topic}</span>
              <span className="meetingMeta">
                {meeting.ticker || "종목 없음"} · {statusLabel(meeting.status)}
              </span>
            </button>
          ))}
          {meetings.length === 0 && <div className="emptyState">아직 생성된 회의가 없습니다.</div>}
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar" id="meetings">
          <div>
            <p className="eyebrow">AI Council 작업공간</p>
            <h2>{selectedMeeting?.topic || "회의를 만들거나 선택하세요"}</h2>
          </div>
          <div className="actions">
            {selectedMeeting?.ticker && <span className="ticker">{selectedMeeting.ticker}</span>}
            <button
              className="secondaryButton"
              type="button"
              disabled={!selectedId || loading}
              onClick={handleRun}
            >
              <Play size={18} aria-hidden="true" />
              회의 실행
            </button>
            <a
              className={`secondaryButton ${detail?.report?.available ? "" : "disabled"}`}
              href={selectedId && detail?.report?.available ? api.reportUrl(selectedId) : undefined}
              target="_blank"
              rel="noreferrer"
            >
              <FileText size={18} aria-hidden="true" />
              리포트
            </a>
          </div>
        </header>

        {error && (
          <div className="errorBanner">
            <AlertTriangle size={18} aria-hidden="true" />
            {error}
          </div>
        )}

        <section className="statusStrip">
          <div>
            <ListChecks size={18} aria-hidden="true" />
            <span>에이전트 {agents.length}명 준비</span>
          </div>
          <div>
            <Shield size={18} aria-hidden="true" />
            <span>브로커/주문 실행 없음</span>
          </div>
          <div>
            <CheckCircle2 size={18} aria-hidden="true" />
            <span>
              {selectedMeeting
                ? `${statusLabel(selectedMeeting.status)} · ${modeLabel(selectedMeeting.mode)}`
                : "준비 완료"}
            </span>
          </div>
        </section>

        <DashboardCards
          health={health}
          marketDataStatus={marketDataStatus}
          telegramStatus={telegramStatus}
          webhookStatus={webhookStatus}
          meetings={meetings}
          tradeReviews={tradeReviews}
        />

        <SettingsGuidePanel health={health} />

        <MarketDataPanel
          status={marketDataStatus}
          ticker={marketDataTicker}
          setTicker={setMarketDataTicker}
          result={marketDataResult}
          loading={marketDataLoading}
          onLookup={handleMarketDataLookup}
        />

        <WebhookPanel
          status={webhookStatus}
          events={webhookEvents}
          tradeReviews={tradeReviews}
          onRefresh={refreshWebhookData}
          onOpenMeeting={handleSelect}
        />

        <section className="tradeReviewSection" id="autonomous-review">
          <div className="tradeReviewHeader">
            <div>
              <p className="eyebrow">Autonomous Trader Review Mode</p>
              <h3>자율 트레이더 검토</h3>
            </div>
            <span>주문 실행 허용 여부: 아니오</span>
          </div>
          <form className="tickerReviewForm" onSubmit={handleAutonomousReviewSubmit}>
            <label>
              <span>후보군</span>
              <select
                value={autonomousReviewForm.universe}
                onChange={(event) => updateAutonomousReviewField("universe", event.target.value)}
              >
                <option value="mock_penny_stocks">mock_penny_stocks</option>
                <option value="mock_momentum_stocks">mock_momentum_stocks</option>
                <option value="mock_watchlist">mock_watchlist</option>
                <option value="custom_stub">custom_stub</option>
              </select>
            </label>
            <label>
              <span>검토 모드</span>
              <select
                value={autonomousReviewForm.review_mode}
                onChange={(event) => updateAutonomousReviewField("review_mode", event.target.value)}
              >
                <option value="penny_stock_risk">페니주 리스크 검토 (penny_stock_risk)</option>
                <option value="momentum_review">모멘텀 검토 (momentum_review)</option>
                <option value="news_catalyst_review">뉴스 촉매 검토 (news_catalyst_review)</option>
                <option value="general_review">일반 검토 (general_review)</option>
              </select>
            </label>
            <label>
              <span>최대 후보 수</span>
              <input
                type="number"
                min="1"
                max="20"
                value={autonomousReviewForm.max_candidates}
                onChange={(event) =>
                  updateAutonomousReviewField("max_candidates", event.target.value)
                }
              />
            </label>
            <label>
              <span>타임프레임</span>
              <input
                value={autonomousReviewForm.timeframe}
                onChange={(event) => updateAutonomousReviewField("timeframe", event.target.value)}
                placeholder="1d"
              />
            </label>
            <label className="wideField">
              <span>메모</span>
              <textarea
                value={autonomousReviewForm.notes}
                onChange={(event) => updateAutonomousReviewField("notes", event.target.value)}
                rows={3}
              />
            </label>
            <button
              className="primaryButton"
              type="submit"
              disabled={autonomousReviewLoading}
            >
              <Shield size={18} aria-hidden="true" />
              자율 검토 시작
            </button>
          </form>
          <p className="contextHint">
            AI Council이 후보 종목을 자동 발굴하고 리스크 검토를 수행합니다. 이 기능은 주문을
            실행하지 않고, 검토와 보고만 수행합니다.
          </p>
          {autonomousReviewResult && (
            <AutonomousReviewResult
              result={autonomousReviewResult}
              onOpenMeeting={handleSelect}
            />
          )}
        </section>

        <section className="tradeReviewSection" id="ticker-review">
          <div className="tradeReviewHeader">
            <div>
              <p className="eyebrow">Phase 11 Ticker-only Auto Research</p>
              <h3>종목 자동 분석</h3>
            </div>
            <span>주문 실행 허용 여부: false</span>
          </div>
          <form className="tickerReviewForm" onSubmit={handleTickerReviewSubmit}>
            <label>
              <span>티커</span>
              <input
                value={tickerReviewForm.ticker}
                onChange={(event) => updateTickerReviewField("ticker", event.target.value)}
                placeholder="TESTA"
                maxLength={16}
              />
            </label>
            <label>
              <span>검토 모드</span>
              <select
                value={tickerReviewForm.review_mode}
                onChange={(event) => updateTickerReviewField("review_mode", event.target.value)}
              >
                <option value="penny_stock_risk">페니주 리스크 검토 (penny_stock_risk)</option>
                <option value="momentum_review">모멘텀 검토 (momentum_review)</option>
                <option value="long_term_review">장기 관점 검토 (long_term_review)</option>
                <option value="news_catalyst_review">뉴스 촉매 검토 (news_catalyst_review)</option>
                <option value="general_review">일반 검토 (general_review)</option>
              </select>
            </label>
            <label>
              <span>타임프레임</span>
              <input
                value={tickerReviewForm.timeframe}
                onChange={(event) => updateTickerReviewField("timeframe", event.target.value)}
                placeholder="1d"
              />
            </label>
            <label className="wideField">
              <span>메모</span>
              <textarea
                value={tickerReviewForm.notes}
                onChange={(event) => updateTickerReviewField("notes", event.target.value)}
                rows={3}
                placeholder="종목만 입력한 자동 리서치 요청"
              />
            </label>
            <button
              className="primaryButton"
              type="submit"
              disabled={tickerReviewLoading || !tickerReviewForm.ticker.trim()}
            >
              <Shield size={18} aria-hidden="true" />
              자동 분석 시작
            </button>
          </form>
          <p className="contextHint">
            티커만 입력하면 AI Council이 mock market data로 기본 payload를 구성해 Risk Gate Review를
            실행합니다. 이 기능은 주문을 실행하지 않습니다.
          </p>
          {tickerReviewResult && (
            <TickerReviewResult result={tickerReviewResult} onOpenMeeting={handleSelect} />
          )}
        </section>

        <section className="tradeReviewSection" id="trade-review">
          <div className="tradeReviewHeader">
            <div>
              <p className="eyebrow">Phase 7 읽기 전용 검토</p>
              <h3>거래 신호 검토</h3>
            </div>
            <span>주문 실행 허용 여부: false</span>
          </div>
          <form className="tradeReviewForm" onSubmit={handleTradeReviewSubmit}>
            <label>
              <span>종목명</span>
              <input
                value={tradeReviewForm.ticker}
                onChange={(event) => updateTradeReviewField("ticker", event.target.value)}
                placeholder="ABCD"
                maxLength={16}
              />
            </label>
            <label>
              <span>전략 신호</span>
              <input
                value={tradeReviewForm.strategy_signal}
                onChange={(event) =>
                  updateTradeReviewField("strategy_signal", event.target.value)
                }
                placeholder="breakout"
              />
            </label>
            <label>
              <span>매수/매도 문맥</span>
              <select
                value={tradeReviewForm.side}
                onChange={(event) => updateTradeReviewField("side", event.target.value)}
              >
                <option value="watch_only">watch_only</option>
                <option value="review_only">review_only</option>
                <option value="buy">buy - 검토 문맥으로만 저장</option>
                <option value="sell">sell - 검토 문맥으로만 저장</option>
              </select>
            </label>
            <label>
              <span>가격</span>
              <input
                type="number"
                step="0.0001"
                min="0"
                value={tradeReviewForm.price}
                onChange={(event) => updateTradeReviewField("price", event.target.value)}
                placeholder="0.82"
              />
            </label>
            <label>
              <span>거래량</span>
              <input
                type="number"
                min="0"
                value={tradeReviewForm.volume}
                onChange={(event) => updateTradeReviewField("volume", event.target.value)}
                placeholder="12500000"
              />
            </label>
            <label>
              <span>타임프레임</span>
              <input
                value={tradeReviewForm.timeframe}
                onChange={(event) => updateTradeReviewField("timeframe", event.target.value)}
                placeholder="1m"
              />
            </label>
            <label>
              <span>스프레드 %</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={tradeReviewForm.spread_pct}
                onChange={(event) => updateTradeReviewField("spread_pct", event.target.value)}
                placeholder="4.5"
              />
            </label>
            <label className="checkboxLabel">
              <input
                type="checkbox"
                checked={tradeReviewForm.premarket}
                onChange={(event) => updateTradeReviewField("premarket", event.target.checked)}
              />
              <span>장전 거래</span>
            </label>
            <label>
              <span>RSI</span>
              <input
                type="number"
                step="0.1"
                value={tradeReviewForm.rsi}
                onChange={(event) => updateTradeReviewField("rsi", event.target.value)}
                placeholder="68"
              />
            </label>
            <label>
              <span>VWAP 거리</span>
              <input
                type="number"
                step="0.001"
                value={tradeReviewForm.vwap_distance}
                onChange={(event) => updateTradeReviewField("vwap_distance", event.target.value)}
                placeholder="0.04"
              />
            </label>
            <label className="wideField">
              <span>뉴스 헤드라인</span>
              <textarea
                value={tradeReviewForm.news_headlines}
                onChange={(event) =>
                  updateTradeReviewField("news_headlines", event.target.value)
                }
                rows={3}
                placeholder="한 줄에 하나씩 입력"
              />
            </label>
            <label className="wideField">
              <span>메모</span>
              <textarea
                value={tradeReviewForm.notes}
                onChange={(event) => updateTradeReviewField("notes", event.target.value)}
                rows={3}
                placeholder="기존 봇이 생성한 후보 신호"
              />
            </label>
            <button
              className="primaryButton"
              type="submit"
              disabled={
                tradeReviewLoading ||
                !tradeReviewForm.ticker.trim() ||
                !tradeReviewForm.strategy_signal.trim()
              }
            >
              <Shield size={18} aria-hidden="true" />
              검토 요청
            </button>
          </form>
          <p className="contextHint">
            거래 신호 검토는 외부 봇의 후보 신호를 읽기 전용 문맥으로만 저장합니다. 주문을 생성,
            전송, 라우팅하지 않습니다.
          </p>
          {tradeReviewResult && (
            <TradeReviewResult
              result={tradeReviewResult}
              onOpenMeeting={handleSelect}
              onSendTelegram={handleSendTradeReviewTelegram}
              telegramResult={tradeReviewTelegramResult}
              telegramConfigured={Boolean(telegramStatus?.configured)}
              loading={tradeReviewLoading}
            />
          )}
          {tradeReviews.length > 0 && (
            <div className="recentTradeReviews">
              <h4>최근 거래 신호 검토</h4>
              <div>
                {tradeReviews.slice(0, 4).map((review) => (
                  <button
                    type="button"
                    key={review.id}
                    onClick={() => handleSelect(review.linked_meeting_id)}
                  >
                    <strong>{review.ticker}</strong>
                    <span>
                      {decisionLabel(review.decision)} · {riskLevelLabel(review.risk_level)} · 주문{" "}
                      {booleanKo(review.order_execution_allowed)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {selectedMeeting ? (
          <section className="detailGrid">
            <div className="outputColumn">
              <DecisionCard decision={structuredDecision} />
              <SafetyBoundary />
              <RoundList messages={messages} />
              <OutputGroup title="에이전트 분석" outputs={groupedOutputs.analysis} />
              <OutputGroup title="비판 검토 반박" outputs={groupedOutputs.rebuttal} />
              <OutputGroup title="의장 요약" outputs={groupedOutputs.summary} />
            </div>

            <aside className="reviewPanel">
              <h3>검토/리스크 구조</h3>
              <dl>
                <div>
                  <dt>회의 모드</dt>
                  <dd>{modeLabel(selectedMeeting.mode)}</dd>
                </div>
                <div>
                  <dt>Mock 전용</dt>
                  <dd>{booleanKo(Boolean(selectedMeeting.trade_review?.mock_only))}</dd>
                </div>
                <div>
                  <dt>주문 실행 허용 여부</dt>
                  <dd>{booleanKo(Boolean(selectedMeeting.trade_review?.order_execution_allowed))}</dd>
                </div>
                <div>
                  <dt>리스크 게이트</dt>
                  <dd>{selectedMeeting.trade_review?.risk_gate_status || "future_required"}</dd>
                </div>
                <div>
                  <dt>브로커 연결</dt>
                  <dd>{selectedMeeting.trade_review?.broker_integration_status || "not_connected"}</dd>
                </div>
              </dl>

              <div className="telegramPanel" id="telegram">
                <div className="panelHeading">
                  <h3>텔레그램 전송</h3>
                  <span>{telegramStatus?.configured ? "켜짐" : "꺼짐"}</span>
                </div>
                <p className="contextHint">
                  {telegramStatus?.configured
                    ? "이 backend에 리포트 전송 설정이 완료되어 있습니다."
                    : "텔레그램이 비활성화되어 있거나 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID가 없습니다."}
                </p>
                <button
                  className="secondaryButton"
                  type="button"
                  disabled={!selectedId || telegramLoading}
                  onClick={handleSendTelegram}
                >
                  <Send size={17} aria-hidden="true" />
                  텔레그램으로 보내기
                </button>
                {telegramResult && (
                  <div className={`telegramResult ${telegramResult.sent ? "sent" : "disabled"}`}>
                    <strong>{telegramResult.status}</strong>
                    <p>{telegramResult.detail}</p>
                  </div>
                )}
              </div>

              <div className="contextPanel">
                <div className="panelHeading">
                  <h3>참고 파일</h3>
                  <span>{contextFiles.length}</span>
                </div>
                <form className="fileUpload" onSubmit={handleUploadFile}>
                  <input
                    type="file"
                    accept=".txt,.md,.csv,.json,.log,.pdf"
                    onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
                  />
                  <button
                    className="secondaryButton"
                    type="submit"
                    disabled={!selectedFile || fileLoading}
                  >
                    <Upload size={17} aria-hidden="true" />
                    업로드
                  </button>
                </form>
                <p className="contextHint">
                  업로드된 파일 요약은 다음 회의 실행 시 참고 문맥으로 포함됩니다.
                </p>
                <div className="fileList">
                  {contextFiles.map((file) => (
                    <div className="fileRow" key={file.id}>
                      <div>
                        <strong>{file.original_filename}</strong>
                        <span>
                          {file.file_type} · {file.status} · {Math.ceil(file.file_size / 1024)} KB
                        </span>
                        <p>{file.summary}</p>
                      </div>
                      <button
                        className="iconButton"
                        type="button"
                        title="파일 삭제"
                        disabled={fileLoading}
                        onClick={() => handleDeleteFile(file.id)}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                  {contextFiles.length === 0 && (
                    <div className="emptyState">첨부된 참고 파일이 없습니다.</div>
                  )}
                </div>
              </div>
            </aside>
          </section>
        ) : (
          <section className="blankSlate">
            <Brain size={44} aria-hidden="true" />
            <h3>선택된 회의가 없습니다.</h3>
            <p>분석 주제를 입력해 AI Council 회의를 시작하세요.</p>
          </section>
        )}
      </main>
    </div>
  );
}

function DashboardCards({ health, marketDataStatus, telegramStatus, webhookStatus, meetings, tradeReviews }) {
  const backendOk = health?.status === "ok";
  const llmProvider = health?.llm_provider || "mock";
  const marketDataProvider =
    marketDataStatus?.active_provider || health?.market_data?.provider || "mock_market_data";
  return (
    <section className="dashboardGrid" id="dashboard">
      <article>
        <span>Backend 상태</span>
        <strong>{backendOk ? "정상" : "확인 필요"}</strong>
        <p>{api.baseUrl}</p>
      </article>
      <article>
        <span>LLM Provider 상태</span>
        <strong>{llmProvider}</strong>
        <p>{llmProvider === "mock" ? "기본 mock provider 사용 중" : "Local/OpenAI 호환 provider 사용 중"}</p>
      </article>
      <article>
        <span>Market Data Provider 상태</span>
        <strong>{marketDataProvider}</strong>
        <p>
          외부 데이터 사용 여부: {booleanKo(Boolean(marketDataStatus?.external_enabled))}
        </p>
      </article>
      <article>
        <span>자율 검토 모드</span>
        <strong>사용 가능</strong>
        <p>자율 후보 발굴 + 자동 검토 + 보고</p>
      </article>
      <article>
        <span>후보 발굴 provider</span>
        <strong>{marketDataProvider}</strong>
        <p>후보군은 mock universe를 기준으로 하며 snapshot provider를 반영합니다.</p>
      </article>
      <article>
        <span>텔레그램 상태</span>
        <strong>{telegramStatus?.configured ? "설정됨" : "비활성화"}</strong>
        <p>보고 전송 전용, 주문 기능 없음</p>
      </article>
      <article>
        <span>웹훅 상태</span>
        <strong>{webhookStatus?.configured ? "수신 가능" : "비활성화"}</strong>
        <p>{webhookStatus?.endpoint_path || "/api/webhooks/trade-signal"}</p>
      </article>
      <article>
        <span>최근 회의 수</span>
        <strong>{meetings.length}</strong>
        <p>회의 목록 기준</p>
      </article>
      <article>
        <span>최근 거래 신호 검토 수</span>
        <strong>{tradeReviews.length}</strong>
        <p>읽기 전용 검토 기록</p>
      </article>
      <article className="safetyCard">
        <span>주문 실행 상태</span>
        <strong>비활성화</strong>
        <p>order_execution_allowed=false</p>
      </article>
    </section>
  );
}

function SettingsGuidePanel({ health }) {
  return (
    <section className="settingsGuide" id="settings-guide">
      <div>
        <p className="eyebrow">설정/가이드</p>
        <h3>Local LLM과 외부 연동 상태</h3>
      </div>
      <dl>
        <div>
          <dt>API 기준 URL</dt>
          <dd>{api.baseUrl}</dd>
        </div>
        <div>
          <dt>현재 LLM Provider</dt>
          <dd>{health?.llm_provider || "mock"}</dd>
        </div>
        <div>
          <dt>현재 Market Data Provider</dt>
          <dd>{health?.market_data?.provider || "mock"}</dd>
        </div>
        <div>
          <dt>Local LLM 전환</dt>
          <dd>LLM_PROVIDER=local_openai_compatible 설정 후 backend를 재시작</dd>
        </div>
        <div>
          <dt>보안</dt>
          <dd>텔레그램 token, 웹훅 secret, API key는 Git에 커밋하지 않습니다.</dd>
        </div>
      </dl>
    </section>
  );
}

function DecisionCard({ decision }) {
  const hasDecision = Boolean(decision?.decision);
  return (
    <section className="decisionCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">구조화된 판단</p>
          <h3>{hasDecision ? decisionLabel(decision.decision) : "대기 중"}</h3>
        </div>
        <div className="badgeGroup">
          <span className={`decisionBadge ${hasDecision ? decision.decision?.toLowerCase() : ""}`}>
            {hasDecision ? decisionLabel(decision.decision) : "초안 (DRAFT)"}
          </span>
          <span className={`riskBadge ${hasDecision ? decision.risk_level : ""}`}>
            {hasDecision ? riskLevelLabel(decision.risk_level) : "미평가"}
          </span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>신뢰도</span>
          <strong>{hasDecision ? Math.round(decision.confidence * 100) : 0}%</strong>
        </div>
        <div>
          <span>거래 검토상 허용 여부</span>
          <strong>{booleanKo(Boolean(decision.trade_allowed))}</strong>
        </div>
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(decision.order_execution_allowed))}</strong>
        </div>
        <div>
          <span>포지션 크기 배수</span>
          <strong>{hasDecision ? decision.position_size_multiplier : 0}</strong>
        </div>
        <div>
          <span>데이터 품질</span>
          <strong>{hasDecision ? dataQualityLabel(decision.data_quality) : "알 수 없음"}</strong>
        </div>
      </div>
      {hasDecision && (
        <div className="decisionLists">
          <div>
            <h4>리스크 플래그</h4>
            {(decision.risk_flags || []).slice(0, 6).map((flag) => (
              <span key={flag}>{flag}</span>
            ))}
          </div>
          <div>
            <h4>추가 확인 필요사항</h4>
            {(decision.required_follow_up || []).slice(0, 4).map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function MarketDataPanel({ status, ticker, setTicker, result, loading, onLookup }) {
  const resultProvider = result?.payload?.provider || result?.payload?.quote?.provider;
  const resultDataQuality = result?.payload?.data_quality || result?.payload?.quote?.data_quality;
  return (
    <section className="tradeReviewSection" id="market-data">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">Phase 13 Yahoo Finance Read-only Provider</p>
          <h3>시장 데이터 상태</h3>
        </div>
        <span>주문 실행 허용 여부: false</span>
      </div>
      <div className="webhookStatusGrid">
        <div>
          <span>현재 Provider</span>
          <strong>{status?.active_provider || "mock_market_data"}</strong>
        </div>
        <div>
          <span>외부 데이터 사용 여부</span>
          <strong>{booleanKo(Boolean(status?.external_calls_allowed ?? status?.external_enabled))}</strong>
        </div>
        <div>
          <span>API 키 설정 여부</span>
          <strong>{booleanKo(Boolean(status?.api_key_configured))}</strong>
        </div>
        <div>
          <span>Yahoo Finance 사용 가능 여부</span>
          <strong>{booleanKo(Boolean(status?.yahoo_finance_available))}</strong>
        </div>
        <div>
          <span>yfinance 설치 여부</span>
          <strong>{booleanKo(Boolean(status?.yfinance_installed))}</strong>
        </div>
        <div>
          <span>상태</span>
          <strong>{status?.last_check_status || "ok"}</strong>
        </div>
        <div>
          <span>Provider 경고</span>
          <strong>{status?.provider_warning || "없음"}</strong>
        </div>
      </div>
      <form className="marketDataLookup" onSubmit={(event) => event.preventDefault()}>
        <label>
          <span>데이터 조회 테스트</span>
          <input
            value={ticker}
            onChange={(event) => setTicker(event.target.value)}
            placeholder="TESTA"
            maxLength={16}
          />
        </label>
        <button
          className="secondaryButton"
          type="button"
          disabled={loading || !ticker.trim()}
          onClick={() => onLookup("quote")}
        >
          종목 Quote 조회
        </button>
        <button
          className="secondaryButton"
          type="button"
          disabled={loading || !ticker.trim()}
          onClick={() => onLookup("snapshot")}
        >
          종목 Snapshot 조회
        </button>
        <button
          className="secondaryButton"
          type="button"
          disabled={loading || !ticker.trim()}
          onClick={() => onLookup("news")}
        >
          뉴스 조회
        </button>
        <button
          className="secondaryButton"
          type="button"
          disabled={loading || !ticker.trim()}
          onClick={() => onLookup("filings")}
        >
          공시 조회
        </button>
      </form>
      <p className="contextHint">
        이 기능은 시장 데이터 조회 전용입니다. 주문을 실행하지 않습니다. 외부 데이터는 지연되거나 부정확할 수 있습니다.
      </p>
      {result && (
        <div className="jsonResult">
          <div className="panelHeading">
            <h3>{result.kind} 결과</h3>
            <span>{booleanKo(Boolean(result.payload?.order_execution_allowed))}</span>
          </div>
          <div className="decisionMetrics compactMetrics">
            <div>
              <span>결과 Provider</span>
              <strong>{resultProvider || "알 수 없음"}</strong>
            </div>
            <div>
              <span>데이터 품질</span>
              <strong>{dataQualityLabel(resultDataQuality)}</strong>
            </div>
          </div>
          <pre>{JSON.stringify(result.payload, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}

function WebhookPanel({ status, events, tradeReviews, onRefresh, onOpenMeeting }) {
  const endpoint = `${api.baseUrl}${status?.endpoint || "/api/webhooks/trade-signal"}`;
  const reviewById = new Map(tradeReviews.map((review) => [review.id, review]));
  return (
    <section className="webhookPanel" id="webhooks">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">외부 봇 웹훅</p>
          <h3>웹훅 수신기</h3>
        </div>
        <button className="iconButton" type="button" title="웹훅 상태 새로고침" onClick={onRefresh}>
          <RefreshCw size={17} aria-hidden="true" />
        </button>
      </div>
      <div className="webhookStatusGrid">
        <div>
          <span>활성화</span>
          <strong>{booleanKo(Boolean(status?.enabled))}</strong>
        </div>
        <div>
          <span>설정 완료</span>
          <strong>{booleanKo(Boolean(status?.configured))}</strong>
        </div>
        <div>
          <span>Secret 필요</span>
          <strong>{booleanKo(Boolean(status?.require_secret))}</strong>
        </div>
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(status?.order_execution_allowed))}</strong>
        </div>
      </div>
      <div className="endpointRow">
        <span>엔드포인트</span>
        <code>{endpoint}</code>
      </div>
      <p className="contextHint">
        Header: {status?.secret_header || "X-AI-Council-Webhook-Secret"}. Secret 값은 UI에 표시하지 않습니다.
      </p>
      {status?.disabled_reason && <p className="contextHint">{status.disabled_reason}</p>}
      <div className="webhookEvents">
        <h4>최근 웹훅 이벤트</h4>
        {events.length > 0 ? (
          events.slice(0, 5).map((event) => {
            const review = reviewById.get(event.trade_review_id);
            return (
              <article key={event.id}>
                <div>
                  <strong>{event.source}</strong>
                  <span>
                    {event.signal_id} · {event.status} · 중복 여부는 API 응답 기준
                  </span>
                </div>
                <div>
                  <span>거래 신호 검토</span>
                  <strong>{event.trade_review_id ? event.trade_review_id.slice(0, 8) : "없음"}</strong>
                </div>
                <button
                  className="secondaryButton"
                  type="button"
                  disabled={!review?.linked_meeting_id}
                  onClick={() => review?.linked_meeting_id && onOpenMeeting(review.linked_meeting_id)}
                >
                  <FileText size={16} aria-hidden="true" />
                  열기
                </button>
              </article>
            );
          })
        ) : (
          <div className="emptyState">아직 웹훅 이벤트가 없습니다.</div>
        )}
      </div>
    </section>
  );
}

function AutonomousReviewResult({ result, onOpenMeeting }) {
  const groups = [
    ["위험 후보", result.results?.filter((item) => item.decision === "BLOCK" || item.risk_level === "critical") || []],
    ["주의 후보", result.results?.filter((item) => item.decision === "HOLD" || item.risk_level === "high") || []],
    ["추가 데이터 필요", result.results?.filter((item) => item.decision === "NEED_MORE_DATA") || []],
    ["검토상 허용", result.results?.filter((item) => item.decision === "ALLOW") || []]
  ];
  return (
    <section className="tradeReviewResultCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">자율 검토 결과</p>
          <h3>
            후보 {result.candidate_count}개 · 주문 실행 허용 여부: 아니오
          </h3>
        </div>
        <div className="badgeGroup">
          <span className="decisionBadge hold">HOLD {result.summary?.hold_count || 0}</span>
          <span className="riskBadge critical">BLOCK {result.summary?.block_count || 0}</span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>후보군</span>
          <strong>{result.universe}</strong>
        </div>
        <div>
          <span>검토 모드</span>
          <strong>{result.review_mode}</strong>
        </div>
        <div>
          <span>검토상 허용</span>
          <strong>{result.summary?.allow_count || 0}</strong>
        </div>
        <div>
          <span>보류</span>
          <strong>{result.summary?.hold_count || 0}</strong>
        </div>
        <div>
          <span>차단</span>
          <strong>{result.summary?.block_count || 0}</strong>
        </div>
        <div>
          <span>추가 데이터 필요</span>
          <strong>{result.summary?.need_more_data_count || 0}</strong>
        </div>
      </div>
      <div className="autonomousGroups">
        {groups.map(([title, items]) => (
          <div className="autonomousGroup" key={title}>
            <h4>{title}</h4>
            {items.length > 0 ? (
              items.map((item) => (
                <article key={`${title}-${item.ticker}-${item.linked_meeting_id}`}>
                  <div>
                    <strong>{item.ticker}</strong>
                    <span>
                      {decisionLabel(item.decision)} · {riskLevelLabel(item.risk_level)} · {item.scan_reason}
                    </span>
                    <span>주문 실행 허용 여부: {booleanKo(Boolean(item.order_execution_allowed))}</span>
                  </div>
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={!item.linked_meeting_id}
                    onClick={() => item.linked_meeting_id && onOpenMeeting(item.linked_meeting_id)}
                  >
                    <FileText size={16} aria-hidden="true" />
                    회의 열기
                  </button>
                </article>
              ))
            ) : (
              <div className="emptyState">해당 후보가 없습니다.</div>
            )}
          </div>
        ))}
      </div>
      <p className="contextHint">
        ALLOW가 나오더라도 검토상 허용일 뿐이며 실제 주문 실행 허용이 아닙니다.
      </p>
    </section>
  );
}

function TickerReviewResult({ result, onOpenMeeting }) {
  const tickerReview = result.ticker_review || {};
  const tradeReview = result.trade_review || {};
  const decision = result.structured_decision || tradeReview.structured_decision || {};
  const marketData = result.market_data || {};
  const linkedMeetingId = tickerReview.linked_meeting_id || tradeReview.linked_meeting_id;
  return (
    <section className="tradeReviewResultCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">자동 분석 결과</p>
          <h3>
            {tickerReview.ticker || tradeReview.ticker} · {decisionLabel(decision.decision)}
          </h3>
        </div>
        <div className="badgeGroup">
          <span className={`decisionBadge ${(decision.decision || "").toLowerCase()}`}>
            {decisionLabel(decision.decision)}
          </span>
          <span className={`riskBadge ${decision.risk_level || ""}`}>
            {riskLevelLabel(decision.risk_level)}
          </span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>리뷰 모드</span>
          <strong>{tickerReview.review_mode || "penny_stock_risk"}</strong>
        </div>
        <div>
          <span>데이터 품질</span>
          <strong>{dataQualityLabel(marketData.data_quality || decision.data_quality)}</strong>
        </div>
        <div>
          <span>사용 provider</span>
          <strong>{marketData.provider || "mock_market_data"}</strong>
        </div>
        <div>
          <span>거래 검토 ID</span>
          <strong>{tickerReview.trade_review_id ? tickerReview.trade_review_id.slice(0, 8) : "없음"}</strong>
        </div>
        <div>
          <span>연결된 회의</span>
          <strong>{linkedMeetingId ? linkedMeetingId.slice(0, 8) : "없음"}</strong>
        </div>
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(result.order_execution_allowed))}</strong>
        </div>
      </div>
      <div className="decisionLists">
        <div>
          <h4>주요 리스크</h4>
          {(decision.risk_flags || []).slice(0, 6).map((flag) => (
            <span key={flag}>{flag}</span>
          ))}
        </div>
        <div>
          <h4>추가 확인 필요사항</h4>
          {(decision.required_follow_up || []).slice(0, 4).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      </div>
      <div className="tradeReviewActions">
        <button
          className="secondaryButton"
          type="button"
          disabled={!linkedMeetingId}
          onClick={() => linkedMeetingId && onOpenMeeting(linkedMeetingId)}
        >
          <FileText size={17} aria-hidden="true" />
          연결된 회의 열기
        </button>
        <a
          className={`secondaryButton ${result.report?.available ? "" : "disabled"}`}
          href={linkedMeetingId && result.report?.available ? api.reportUrl(linkedMeetingId) : undefined}
          target="_blank"
          rel="noreferrer"
        >
          <FileText size={17} aria-hidden="true" />
          리포트
        </a>
      </div>
    </section>
  );
}

function TradeReviewResult({
  result,
  onOpenMeeting,
  onSendTelegram,
  telegramResult,
  telegramConfigured,
  loading
}) {
  const review = result.trade_review || {};
  const decision = result.structured_decision || review.structured_decision || {};
  const linkedMeetingId = review.linked_meeting_id || result.meeting?.id;
  return (
    <section className="tradeReviewResultCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">검토 결과</p>
          <h3>
            {review.ticker} · {decisionLabel(decision.decision || review.decision)}
          </h3>
        </div>
        <div className="badgeGroup">
          <span className={`decisionBadge ${(decision.decision || review.decision || "").toLowerCase()}`}>
            {decisionLabel(decision.decision || review.decision)}
          </span>
          <span className={`riskBadge ${decision.risk_level || review.risk_level}`}>
            {riskLevelLabel(decision.risk_level || review.risk_level)}
          </span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>신뢰도</span>
          <strong>{decision.confidence ? Math.round(decision.confidence * 100) : 0}%</strong>
        </div>
        <div>
          <span>거래 검토상 허용 여부</span>
          <strong>{booleanKo(Boolean(decision.trade_allowed))}</strong>
        </div>
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(decision.order_execution_allowed))}</strong>
        </div>
        <div>
          <span>연결된 회의</span>
          <strong>{linkedMeetingId ? linkedMeetingId.slice(0, 8) : "없음"}</strong>
        </div>
        <div>
          <span>데이터 품질</span>
          <strong>{dataQualityLabel(decision.data_quality)}</strong>
        </div>
      </div>
      <div className="decisionLists">
        <div>
          <h4>리스크 플래그</h4>
          {(decision.risk_flags || []).slice(0, 6).map((flag) => (
            <span key={flag}>{flag}</span>
          ))}
        </div>
        <div>
          <h4>추가 확인 필요사항</h4>
          {(decision.required_follow_up || []).slice(0, 4).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      </div>
      <div className="tradeReviewActions">
        <button
          className="secondaryButton"
          type="button"
          disabled={!linkedMeetingId}
          onClick={() => linkedMeetingId && onOpenMeeting(linkedMeetingId)}
        >
          <FileText size={17} aria-hidden="true" />
          연결된 회의 열기
        </button>
        <a
          className={`secondaryButton ${result.report?.available ? "" : "disabled"}`}
          href={linkedMeetingId && result.report?.available ? api.reportUrl(linkedMeetingId) : undefined}
          target="_blank"
          rel="noreferrer"
        >
          <FileText size={17} aria-hidden="true" />
          리포트
        </a>
        <button
          className="secondaryButton"
          type="button"
          disabled={!review.id || loading}
          onClick={onSendTelegram}
        >
          <Send size={17} aria-hidden="true" />
          검토 결과 보내기
        </button>
      </div>
      <p className="contextHint">
        텔레그램 상태: {telegramConfigured ? "설정 완료" : "비활성화 또는 설정 누락"}
      </p>
      {telegramResult && (
        <div className={`telegramResult ${telegramResult.sent ? "sent" : "disabled"}`}>
          <strong>{telegramResult.status}</strong>
          <p>{telegramResult.detail}</p>
        </div>
      )}
    </section>
  );
}

function SafetyBoundary() {
  return (
    <section className="safetyBoundary">
      <Shield size={18} aria-hidden="true" />
      <p>
        <strong>안전 경계:</strong> {KOREAN_SAFETY_BOUNDARY}
        <br />
        <span>{SAFETY_BOUNDARY}</span>
      </p>
    </section>
  );
}

function RoundList({ messages }) {
  const rounds = Object.entries(ROUND_LABELS);
  return (
    <section className="roundPanel">
      <h3>토론 라운드</h3>
      {rounds.map(([round, title]) => {
        const roundMessages = messages.filter((message) => message.round === round);
        return (
          <div className="roundGroup" key={round}>
            <h4>{title}</h4>
            {roundMessages.length > 0 ? (
              roundMessages.map((message) => (
                <article className="roundMessage" key={message.id || `${round}-${message.agent_key}`}>
                  <div>
                    <strong>{agentLabel(message.agent_name)}</strong>
                    <span>
                      {messageTypeLabel(message.message_type)} · {riskLevelLabel(message.risk_level)} ·{" "}
                      {Math.round(message.confidence * 100)}%
                    </span>
                  </div>
                  <p>{message.content}</p>
                </article>
              ))
            ) : (
              <div className="emptyState">회의를 실행하면 이 라운드가 생성됩니다.</div>
            )}
          </div>
        );
      })}
    </section>
  );
}

function OutputGroup({ title, outputs }) {
  return (
    <section className="outputGroup">
      <h3>{title}</h3>
      {outputs.length > 0 ? (
        <div className="outputList">
          {outputs.map((output) => (
            <article className="outputCard" key={output.id}>
              <div className="outputHeader">
                <span className="stageIcon">{stageIcon(output.stage)}</span>
                <div>
                  <h4>{agentLabel(output.agent_name)}</h4>
                  <p>{output.stance} · 신뢰도 {Math.round(output.confidence * 100)}%</p>
                </div>
              </div>
              <p className="outputContent">{output.content}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="emptyState">회의를 실행하면 이 섹션이 생성됩니다.</div>
      )}
    </section>
  );
}
