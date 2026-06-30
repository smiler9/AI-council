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
  unavailable: "사용 불가",
  mock: "Mock 데이터"
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

const SCHEDULE_CADENCE_LABELS = {
  manual_only: "수동 실행 전용",
  daily: "매일",
  weekdays: "평일",
  hourly_stub: "1시간마다 (stub)",
  market_open_stub: "장 시작 전 (stub)",
  market_close_stub: "장 마감 후 (stub)"
};

const MESSAGE_TYPE_LABELS = {
  analysis: "분석",
  rebuttal: "반박",
  revision: "수정",
  summary: "요약",
  decision: "판단"
};

const WEBHOOK_PREVIEW_SAMPLE = JSON.stringify(
  {
    source: "us_trader_oracle",
    signal_id: "us_trader_oracle_preview_001",
    symbol: "TESTA",
    signal: "breakout",
    action: "buy",
    price: 0.82,
    volume: 12500000,
    timeframe: "1m",
    indicators: {
      rsi: 68,
      relative_volume: 5.2
    },
    news: ["Mock US Trader Oracle compatibility headline"],
    risk: {
      spread_pct: 4.5,
      premarket: true
    },
    quantity: 1000,
    order_type: "limit"
  },
  null,
  2
);

const WEBHOOK_PROFILE_OPTIONS = [
  ["us_trader_oracle_v1", "US Trader Oracle v1"],
  ["generic", "Generic"],
  ["penny_bot_v1", "Penny Bot v1"],
  ["minimal_signal", "Minimal signal"],
  ["raw", "Profile 없이 raw payload"]
];

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

function scheduleCadenceLabel(value) {
  return SCHEDULE_CADENCE_LABELS[value] ? `${SCHEDULE_CADENCE_LABELS[value]} (${value})` : value;
}

function scheduleRunStatusLabel(value) {
  const labels = {
    completed: "완료",
    failed: "실패",
    skipped: "건너뜀",
    telegram_disabled: "텔레그램 비활성화"
  };
  return labels[value] ? `${labels[value]} (${value})` : value || "알 수 없음";
}

function booleanKo(value) {
  return value ? "예 (true)" : "아니오 (false)";
}

function formatDateTime(value) {
  if (!value) return "없음";
  try {
    return new Intl.DateTimeFormat("ko-KR", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "Asia/Seoul"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function App() {
  const [agents, setAgents] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [tradeReviews, setTradeReviews] = useState([]);
  const [watchlists, setWatchlists] = useState([]);
  const [paperPortfolios, setPaperPortfolios] = useState([]);
  const [watchlistReviews, setWatchlistReviews] = useState([]);
  const [watchlistSchedules, setWatchlistSchedules] = useState([]);
  const [watchlistScheduleRuns, setWatchlistScheduleRuns] = useState([]);
  const [health, setHealth] = useState(null);
  const [marketDataStatus, setMarketDataStatus] = useState(null);
  const [riskEventStatus, setRiskEventStatus] = useState(null);
  const [webhookStatus, setWebhookStatus] = useState(null);
  const [webhookEvents, setWebhookEvents] = useState([]);
  const [webhookPreviewInput, setWebhookPreviewInput] = useState(WEBHOOK_PREVIEW_SAMPLE);
  const [webhookPreviewProfile, setWebhookPreviewProfile] = useState("us_trader_oracle_v1");
  const [webhookPreviewResult, setWebhookPreviewResult] = useState(null);
  const [operationsSummary, setOperationsSummary] = useState(null);
  const [operationsRiskBrief, setOperationsRiskBrief] = useState(null);
  const [operationsScheduleHealth, setOperationsScheduleHealth] = useState(null);
  const [operationsTelegramResult, setOperationsTelegramResult] = useState(null);
  const [diagnosticsSummary, setDiagnosticsSummary] = useState(null);
  const [diagnosticsSecurity, setDiagnosticsSecurity] = useState(null);
  const [diagnosticsProviders, setDiagnosticsProviders] = useState(null);
  const [diagnosticsRuntime, setDiagnosticsRuntime] = useState(null);
  const [diagnosticsE2EStatus, setDiagnosticsE2EStatus] = useState(null);
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
  const [watchlistForm, setWatchlistForm] = useState({
    name: "Penny Stock Watchlist",
    description: "관심 penny stock 후보군",
    tickers: "TESTA\nTESTB\nTESTC\nTESTD\nTESTE",
    review_mode: "penny_stock_risk"
  });
  const [scheduleForm, setScheduleForm] = useState({
    watchlist_id: "",
    name: "매일 장전 리스크 점검",
    enabled: true,
    cadence: "daily",
    run_time: "08:30",
    timezone: "Asia/Seoul",
    auto_send_telegram: false
  });
  const [paperPortfolioForm, setPaperPortfolioForm] = useState({
    name: "AI Council Paper Portfolio",
    description: "실제 주문 없는 가상 검증용 포트폴리오",
    starting_cash: "10000"
  });
  const [paperSimulationForm, setPaperSimulationForm] = useState({
    source_type: "trade_review",
    source_id: "",
    simulation_policy: "risk_gate_conservative",
    max_notional_per_trade: "100",
    slippage_bps: "25",
    spread_bps: "50",
    max_spread_pct: "5",
    take_profit_pct: "8",
    stop_loss_pct: "5",
    allow_only_decision: false
  });
  const [paperExitForm, setPaperExitForm] = useState({
    exit_reason: "manual_simulated_exit",
    exit_price: "",
    slippage_bps: "25",
    spread_bps: "50"
  });
  const [selectedWatchlistId, setSelectedWatchlistId] = useState(null);
  const [selectedPaperPortfolioId, setSelectedPaperPortfolioId] = useState(null);
  const [paperPortfolioDetail, setPaperPortfolioDetail] = useState(null);
  const [paperSimulationResult, setPaperSimulationResult] = useState(null);
  const [paperExitResult, setPaperExitResult] = useState(null);
  const [paperExitEvaluationResult, setPaperExitEvaluationResult] = useState(null);
  const [paperPerformance, setPaperPerformance] = useState(null);
  const [paperPerformanceByStrategy, setPaperPerformanceByStrategy] = useState(null);
  const [paperPerformanceByDecision, setPaperPerformanceByDecision] = useState(null);
  const [paperPerformanceByRiskEvent, setPaperPerformanceByRiskEvent] = useState(null);
  const [paperPerformanceByWatchlist, setPaperPerformanceByWatchlist] = useState(null);
  const [paperPerformanceReport, setPaperPerformanceReport] = useState(null);
  const [marketDataTicker, setMarketDataTicker] = useState("TESTA");
  const [marketDataResult, setMarketDataResult] = useState(null);
  const [riskEventTicker, setRiskEventTicker] = useState("TESTB");
  const [riskEventResult, setRiskEventResult] = useState(null);
  const [tradeReviewResult, setTradeReviewResult] = useState(null);
  const [tickerReviewResult, setTickerReviewResult] = useState(null);
  const [autonomousReviewResult, setAutonomousReviewResult] = useState(null);
  const [watchlistReviewResult, setWatchlistReviewResult] = useState(null);
  const [watchlistTelegramResult, setWatchlistTelegramResult] = useState(null);
  const [scheduleRunResult, setScheduleRunResult] = useState(null);
  const [tradeReviewTelegramResult, setTradeReviewTelegramResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tradeReviewLoading, setTradeReviewLoading] = useState(false);
  const [tickerReviewLoading, setTickerReviewLoading] = useState(false);
  const [autonomousReviewLoading, setAutonomousReviewLoading] = useState(false);
  const [watchlistLoading, setWatchlistLoading] = useState(false);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [paperLoading, setPaperLoading] = useState(false);
  const [operationsLoading, setOperationsLoading] = useState(false);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [marketDataLoading, setMarketDataLoading] = useState(false);
  const [riskEventLoading, setRiskEventLoading] = useState(false);
  const [webhookPreviewLoading, setWebhookPreviewLoading] = useState(false);
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
      const [
        healthStatus,
        marketStatus,
        riskStatus,
        agentList,
        telegram,
        reviewList,
        watchlistList,
        paperPortfolioList,
        watchlistReviewList,
        scheduleList,
        scheduleRunList,
        opsSummary,
        riskBrief,
        scheduleHealth,
        diagSummary,
        diagSecurity,
        diagProviders,
        diagRuntime,
        diagE2EStatus,
        hooks,
        events
      ] = await Promise.all([
        api.getHealth(),
        api.getMarketDataStatus(),
        api.getRiskEventStatus(),
        api.getAgents(),
        api.getTelegramStatus(),
        api.getTradeReviews(),
        api.getWatchlists(),
        api.getPaperPortfolios(),
        api.getWatchlistReviews(),
        api.getWatchlistSchedules(),
        api.getWatchlistScheduleRuns(),
        api.getOperationsSummary(),
        api.getOperationsRiskBrief(),
        api.getOperationsScheduleHealth(),
        api.getDiagnosticsSummary(),
        api.getDiagnosticsSecurity(),
        api.getDiagnosticsProviders(),
        api.getDiagnosticsRuntime(),
        api.getDiagnosticsE2EStatus(),
        api.getWebhookStatus(),
        api.getWebhookEvents()
      ]);
      setHealth(healthStatus);
      setMarketDataStatus(marketStatus);
      setRiskEventStatus(riskStatus);
      setAgents(agentList);
      setTelegramStatus(telegram);
      setTradeReviews(reviewList);
      setWatchlists(watchlistList);
      setPaperPortfolios(paperPortfolioList);
      setWatchlistReviews(watchlistReviewList);
      setSelectedWatchlistId((current) => current || watchlistList[0]?.id || null);
      const nextPaperPortfolioId = paperPortfolioList[0]?.id || null;
      setSelectedPaperPortfolioId((current) => current || nextPaperPortfolioId);
      if (nextPaperPortfolioId) {
        setPaperPortfolioDetail(await api.getPaperPortfolio(nextPaperPortfolioId));
      }
      setWatchlistSchedules(scheduleList);
      setWatchlistScheduleRuns(scheduleRunList);
      setOperationsSummary(opsSummary);
      setOperationsRiskBrief(riskBrief);
      setOperationsScheduleHealth(scheduleHealth);
      setDiagnosticsSummary(diagSummary);
      setDiagnosticsSecurity(diagSecurity);
      setDiagnosticsProviders(diagProviders);
      setDiagnosticsRuntime(diagRuntime);
      setDiagnosticsE2EStatus(diagE2EStatus);
      setScheduleForm((current) => ({
        ...current,
        watchlist_id: current.watchlist_id || watchlistList[0]?.id || ""
      }));
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

  function updateWatchlistField(field, value) {
    setWatchlistForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function updateScheduleField(field, value) {
    setScheduleForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function updatePaperPortfolioField(field, value) {
    setPaperPortfolioForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function updatePaperSimulationField(field, value) {
    setPaperSimulationForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function updatePaperExitField(field, value) {
    setPaperExitForm((current) => ({
      ...current,
      [field]: value
    }));
  }

  function parseWatchlistTickers(value) {
    return value
      .split(/[\n,]/)
      .map((item) => item.trim().toUpperCase())
      .filter(Boolean);
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
      await refreshOperationsData();
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
      await refreshOperationsData();
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
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setAutonomousReviewLoading(false);
    }
  }

  async function handleWatchlistCreate(event) {
    event.preventDefault();
    if (!watchlistForm.name.trim()) return;
    setWatchlistLoading(true);
    setError("");
    try {
      const watchlist = await api.createWatchlist({
        name: watchlistForm.name.trim(),
        description: watchlistForm.description.trim() || null,
        tickers: parseWatchlistTickers(watchlistForm.tickers),
        review_mode: watchlistForm.review_mode
      });
      const nextWatchlists = await api.getWatchlists();
      setWatchlists(nextWatchlists);
      setSelectedWatchlistId(watchlist.id);
      setScheduleForm((current) => ({ ...current, watchlist_id: watchlist.id }));
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setWatchlistLoading(false);
    }
  }

  async function handleWatchlistDelete(watchlistId) {
    setWatchlistLoading(true);
    setError("");
    try {
      await api.deleteWatchlist(watchlistId);
      const nextWatchlists = await api.getWatchlists();
      setWatchlists(nextWatchlists);
      setSelectedWatchlistId(nextWatchlists[0]?.id || null);
      setScheduleForm((current) => ({ ...current, watchlist_id: nextWatchlists[0]?.id || "" }));
      await refreshScheduleData();
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setWatchlistLoading(false);
    }
  }

  async function handleWatchlistRun(watchlistId = selectedWatchlistId) {
    if (!watchlistId) return;
    setWatchlistLoading(true);
    setWatchlistTelegramResult(null);
    setError("");
    try {
      const result = await api.runWatchlistReview(watchlistId);
      setWatchlistReviewResult(result);
      setWatchlistReviews(await api.getWatchlistReviews());
      setTradeReviews(await api.getTradeReviews());
      const firstMeetingId = result.results?.[0]?.linked_meeting_id;
      if (firstMeetingId) {
        await loadMeetings(firstMeetingId);
      }
      await refreshScheduleData();
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setWatchlistLoading(false);
    }
  }

  async function handleWatchlistTelegramSend() {
    const reviewId = watchlistReviewResult?.id;
    if (!reviewId) return;
    setWatchlistLoading(true);
    setWatchlistTelegramResult(null);
    setError("");
    try {
      const result = await api.sendWatchlistReviewTelegram(reviewId);
      setWatchlistTelegramResult(result);
      await refreshTelegramStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setWatchlistLoading(false);
    }
  }

  async function refreshScheduleData() {
    try {
      const [scheduleList, scheduleRunList, watchlistReviewList] = await Promise.all([
        api.getWatchlistSchedules(),
        api.getWatchlistScheduleRuns(),
        api.getWatchlistReviews()
      ]);
      setWatchlistSchedules(scheduleList);
      setWatchlistScheduleRuns(scheduleRunList);
      setWatchlistReviews(watchlistReviewList);
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshOperationsData() {
    setOperationsLoading(true);
    setError("");
    try {
      const [opsSummary, riskBrief, scheduleHealth] = await Promise.all([
        api.getOperationsSummary(),
        api.getOperationsRiskBrief(),
        api.getOperationsScheduleHealth()
      ]);
      setOperationsSummary(opsSummary);
      setOperationsRiskBrief(riskBrief);
      setOperationsScheduleHealth(scheduleHealth);
    } catch (err) {
      setError(err.message);
    } finally {
      setOperationsLoading(false);
    }
  }

  async function refreshDiagnosticsData() {
    setDiagnosticsLoading(true);
    setError("");
    try {
      const [diagSummary, diagSecurity, diagProviders, diagRuntime, diagE2EStatus] =
        await Promise.all([
          api.getDiagnosticsSummary(),
          api.getDiagnosticsSecurity(),
          api.getDiagnosticsProviders(),
          api.getDiagnosticsRuntime(),
          api.getDiagnosticsE2EStatus()
        ]);
      setDiagnosticsSummary(diagSummary);
      setDiagnosticsSecurity(diagSecurity);
      setDiagnosticsProviders(diagProviders);
      setDiagnosticsRuntime(diagRuntime);
      setDiagnosticsE2EStatus(diagE2EStatus);
    } catch (err) {
      setError(err.message);
    } finally {
      setDiagnosticsLoading(false);
    }
  }

  async function handleOperationsRiskBriefTelegram() {
    setOperationsLoading(true);
    setOperationsTelegramResult(null);
    setError("");
    try {
      const result = await api.sendOperationsRiskBriefTelegram();
      setOperationsTelegramResult(result);
      await refreshTelegramStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setOperationsLoading(false);
    }
  }

  async function handleScheduleCreate(event) {
    event.preventDefault();
    const watchlistId = scheduleForm.watchlist_id || selectedWatchlistId;
    if (!watchlistId || !scheduleForm.name.trim()) return;
    setScheduleLoading(true);
    setScheduleRunResult(null);
    setError("");
    try {
      const schedule = await api.createWatchlistSchedule(watchlistId, {
        name: scheduleForm.name.trim(),
        enabled: Boolean(scheduleForm.enabled),
        cadence: scheduleForm.cadence,
        run_time: scheduleForm.run_time.trim() || null,
        timezone: scheduleForm.timezone.trim() || "Asia/Seoul",
        auto_send_telegram: Boolean(scheduleForm.auto_send_telegram)
      });
      setScheduleForm((current) => ({ ...current, watchlist_id: schedule.watchlist_id }));
      await refreshScheduleData();
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setScheduleLoading(false);
    }
  }

  async function handleScheduleDelete(scheduleId) {
    setScheduleLoading(true);
    setError("");
    try {
      await api.deleteWatchlistSchedule(scheduleId);
      await refreshScheduleData();
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setScheduleLoading(false);
    }
  }

  async function handleScheduleRunNow(scheduleId) {
    setScheduleLoading(true);
    setScheduleRunResult(null);
    setError("");
    try {
      const result = await api.runWatchlistScheduleNow(scheduleId);
      setScheduleRunResult(result);
      setWatchlistReviewResult(result.review);
      setWatchlistReviews(await api.getWatchlistReviews());
      setTradeReviews(await api.getTradeReviews());
      await refreshScheduleData();
      const firstMeetingId = result.review?.results?.[0]?.linked_meeting_id;
      if (firstMeetingId) {
        await loadMeetings(firstMeetingId);
      }
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setScheduleLoading(false);
    }
  }

  async function handleScheduleRunDue() {
    setScheduleLoading(true);
    setScheduleRunResult(null);
    setError("");
    try {
      const result = await api.runDueWatchlistSchedules();
      setScheduleRunResult(result);
      setWatchlistReviews(await api.getWatchlistReviews());
      setTradeReviews(await api.getTradeReviews());
      await refreshScheduleData();
      const firstMeetingId = result.results?.[0]?.review?.results?.[0]?.linked_meeting_id;
      if (firstMeetingId) {
        await loadMeetings(firstMeetingId);
      }
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setScheduleLoading(false);
    }
  }

  async function refreshPaperData(portfolioId = selectedPaperPortfolioId) {
    try {
      const portfolios = await api.getPaperPortfolios();
      setPaperPortfolios(portfolios);
      const nextId = portfolioId || portfolios[0]?.id || null;
      setSelectedPaperPortfolioId(nextId);
      if (nextId) {
        setPaperPortfolioDetail(await api.getPaperPortfolio(nextId));
      } else {
        setPaperPortfolioDetail(null);
      }
    } catch (err) {
      setError(err.message);
    }
  }

  async function refreshPaperPerformance(portfolioId = selectedPaperPortfolioId) {
    if (!portfolioId) {
      setPaperPerformance(null);
      setPaperPerformanceByStrategy(null);
      setPaperPerformanceByDecision(null);
      setPaperPerformanceByRiskEvent(null);
      setPaperPerformanceByWatchlist(null);
      return;
    }
    const [summary, byStrategy, byDecision, byRiskEvent, byWatchlist] = await Promise.all([
      api.getPaperPerformance(portfolioId),
      api.getPaperPerformanceByStrategy(portfolioId),
      api.getPaperPerformanceByDecision(portfolioId),
      api.getPaperPerformanceByRiskEvent(portfolioId),
      api.getPaperPerformanceByWatchlist(portfolioId)
    ]);
    setPaperPerformance(summary);
    setPaperPerformanceByStrategy(byStrategy);
    setPaperPerformanceByDecision(byDecision);
    setPaperPerformanceByRiskEvent(byRiskEvent);
    setPaperPerformanceByWatchlist(byWatchlist);
  }

  async function handlePaperPortfolioCreate(event) {
    event.preventDefault();
    if (!paperPortfolioForm.name.trim()) return;
    setPaperLoading(true);
    setError("");
    try {
      const portfolio = await api.createPaperPortfolio({
        name: paperPortfolioForm.name.trim(),
        description: paperPortfolioForm.description.trim() || null,
        starting_cash: Number(paperPortfolioForm.starting_cash) || 10000
      });
      await refreshPaperData(portfolio.id);
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
    }
  }

  async function handlePaperPortfolioDelete(portfolioId) {
    setPaperLoading(true);
    setError("");
    try {
      await api.deletePaperPortfolio(portfolioId);
      await refreshPaperData(null);
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
    }
  }

  async function handlePaperPortfolioSelect(portfolioId) {
    setSelectedPaperPortfolioId(portfolioId);
    setPaperSimulationResult(null);
    setPaperExitResult(null);
    setPaperExitEvaluationResult(null);
    setPaperPerformanceReport(null);
    setError("");
    try {
      setPaperPortfolioDetail(await api.getPaperPortfolio(portfolioId));
      await refreshPaperPerformance(portfolioId);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handlePaperSimulationSubmit(event) {
    event.preventDefault();
    if (!selectedPaperPortfolioId || !paperSimulationForm.source_id.trim()) return;
    setPaperLoading(true);
    setPaperSimulationResult(null);
    setPaperExitResult(null);
    setPaperExitEvaluationResult(null);
    setError("");
    try {
      const result = await api.simulatePaperReview(selectedPaperPortfolioId, {
        source_type: paperSimulationForm.source_type,
        source_id: paperSimulationForm.source_id.trim(),
        simulation_policy: paperSimulationForm.simulation_policy,
        max_notional_per_trade: Number(paperSimulationForm.max_notional_per_trade) || 100,
        slippage_bps: Number(paperSimulationForm.slippage_bps) || 0,
        spread_bps: Number(paperSimulationForm.spread_bps) || 0,
        max_spread_pct: Number(paperSimulationForm.max_spread_pct) || 5,
        take_profit_pct: Number(paperSimulationForm.take_profit_pct) || 8,
        stop_loss_pct: Number(paperSimulationForm.stop_loss_pct) || 5,
        simulation_only: true,
        allow_only_decision: Boolean(paperSimulationForm.allow_only_decision)
      });
      setPaperSimulationResult(result);
      await refreshPaperData(selectedPaperPortfolioId);
      await refreshPaperPerformance(selectedPaperPortfolioId);
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
    }
  }

  async function handlePaperPositionExit(positionId) {
    if (!selectedPaperPortfolioId || !positionId) return;
    setPaperLoading(true);
    setPaperExitResult(null);
    setError("");
    try {
      const result = await api.simulatePaperExit(selectedPaperPortfolioId, positionId, {
        exit_reason: paperExitForm.exit_reason,
        exit_price: paperExitForm.exit_price ? Number(paperExitForm.exit_price) : null,
        slippage_bps: Number(paperExitForm.slippage_bps) || 0,
        spread_bps: Number(paperExitForm.spread_bps) || 0,
        simulation_only: true
      });
      setPaperExitResult(result);
      await refreshPaperData(selectedPaperPortfolioId);
      await refreshPaperPerformance(selectedPaperPortfolioId);
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
    }
  }

  async function handlePaperEvaluateExits(executeSimulatedExits = false) {
    if (!selectedPaperPortfolioId) return;
    setPaperLoading(true);
    setPaperExitEvaluationResult(null);
    setError("");
    try {
      const result = await api.evaluatePaperExits(selectedPaperPortfolioId, {
        execute_simulated_exits: executeSimulatedExits,
        take_profit_pct: Number(paperSimulationForm.take_profit_pct) || 8,
        stop_loss_pct: Number(paperSimulationForm.stop_loss_pct) || 5,
        slippage_bps: Number(paperExitForm.slippage_bps) || 0,
        spread_bps: Number(paperExitForm.spread_bps) || 0,
        simulation_only: true
      });
      setPaperExitEvaluationResult(result);
      await refreshPaperData(selectedPaperPortfolioId);
      await refreshPaperPerformance(selectedPaperPortfolioId);
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
    }
  }

  async function handlePaperPerformanceRefresh() {
    if (!selectedPaperPortfolioId) return;
    setPaperLoading(true);
    setError("");
    try {
      await refreshPaperPerformance(selectedPaperPortfolioId);
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
    }
  }

  async function handlePaperPerformanceReport() {
    if (!selectedPaperPortfolioId) return;
    setPaperLoading(true);
    setPaperPerformanceReport(null);
    setError("");
    try {
      const report = await api.createPaperPerformanceReport(selectedPaperPortfolioId);
      setPaperPerformanceReport(report);
      await refreshPaperPerformance(selectedPaperPortfolioId);
      await refreshOperationsData();
    } catch (err) {
      setError(err.message);
    } finally {
      setPaperLoading(false);
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

  async function handleRiskEventLookup(kind) {
    const tickerValue = riskEventTicker.trim();
    if (!tickerValue) return;
    setRiskEventLoading(true);
    setError("");
    try {
      const requestMap = {
        news: api.getRiskEventNews,
        filings: api.getRiskEventFilings,
        detect: api.getRiskEventDetection
      };
      const payload = await requestMap[kind](tickerValue);
      setRiskEventResult({ kind, payload });
      setRiskEventStatus(await api.getRiskEventStatus());
    } catch (err) {
      setError(err.message);
    } finally {
      setRiskEventLoading(false);
    }
  }

  async function handleWebhookPreview() {
    setWebhookPreviewLoading(true);
    setWebhookPreviewResult(null);
    setError("");
    try {
      const payload = JSON.parse(webhookPreviewInput);
      const requestPayload =
        webhookPreviewProfile === "raw" || (payload.profile && payload.payload)
          ? payload
          : {
              profile: webhookPreviewProfile,
              payload
            };
      const result = await api.normalizeWebhookPreview(requestPayload);
      setWebhookPreviewResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setWebhookPreviewLoading(false);
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
          <a href="#diagnostics">운영 진단</a>
          <a href="#meetings">회의</a>
          <a href="#market-data">시장 데이터 상태</a>
          <a href="#risk-events">뉴스/공시 리스크</a>
          <a href="#watchlists">관심종목</a>
          <a href="#watchlist-schedules">자동 분석 스케줄</a>
          <a href="#paper-trading">가상 검증</a>
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

        <OperationsDashboardPanel
          summary={operationsSummary}
          riskBrief={operationsRiskBrief}
          scheduleHealth={operationsScheduleHealth}
          telegramStatus={telegramStatus}
          webhookStatus={webhookStatus}
          telegramResult={operationsTelegramResult}
          loading={operationsLoading}
          diagnosticsSummary={diagnosticsSummary}
          diagnosticsSecurity={diagnosticsSecurity}
          diagnosticsProviders={diagnosticsProviders}
          diagnosticsE2EStatus={diagnosticsE2EStatus}
          onRefresh={refreshOperationsData}
          onSendTelegram={handleOperationsRiskBriefTelegram}
          onOpenMeeting={handleSelect}
        />

        <DiagnosticsPanel
          summary={diagnosticsSummary}
          security={diagnosticsSecurity}
          providers={diagnosticsProviders}
          runtime={diagnosticsRuntime}
          e2eStatus={diagnosticsE2EStatus}
          loading={diagnosticsLoading}
          onRefresh={refreshDiagnosticsData}
        />

        <DashboardCards
          health={health}
          marketDataStatus={marketDataStatus}
          riskEventStatus={riskEventStatus}
          telegramStatus={telegramStatus}
          webhookStatus={webhookStatus}
          meetings={meetings}
          tradeReviews={tradeReviews}
          watchlists={watchlists}
          watchlistReviews={watchlistReviews}
          watchlistSchedules={watchlistSchedules}
          watchlistScheduleRuns={watchlistScheduleRuns}
          paperPortfolios={paperPortfolios}
          operationsSummary={operationsSummary}
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

        <RiskEventPanel
          status={riskEventStatus}
          ticker={riskEventTicker}
          setTicker={setRiskEventTicker}
          result={riskEventResult}
          loading={riskEventLoading}
          onLookup={handleRiskEventLookup}
        />

        <WatchlistPanel
          watchlists={watchlists}
          selectedWatchlistId={selectedWatchlistId}
          setSelectedWatchlistId={setSelectedWatchlistId}
          form={watchlistForm}
          updateField={updateWatchlistField}
          loading={watchlistLoading}
          result={watchlistReviewResult}
          telegramResult={watchlistTelegramResult}
          telegramConfigured={Boolean(telegramStatus?.configured)}
          onCreate={handleWatchlistCreate}
          onDelete={handleWatchlistDelete}
          onRun={handleWatchlistRun}
          onSendTelegram={handleWatchlistTelegramSend}
          onOpenMeeting={handleSelect}
        />

        <WatchlistSchedulePanel
          watchlists={watchlists}
          schedules={watchlistSchedules}
          runs={watchlistScheduleRuns}
          form={scheduleForm}
          updateField={updateScheduleField}
          loading={scheduleLoading}
          result={scheduleRunResult}
          telegramConfigured={Boolean(telegramStatus?.configured)}
          onCreate={handleScheduleCreate}
          onDelete={handleScheduleDelete}
          onRunNow={handleScheduleRunNow}
          onRunDue={handleScheduleRunDue}
          onOpenMeeting={handleSelect}
        />

        <PaperTradingPanel
          portfolios={paperPortfolios}
          selectedPortfolioId={selectedPaperPortfolioId}
          detail={paperPortfolioDetail}
          portfolioForm={paperPortfolioForm}
          simulationForm={paperSimulationForm}
          exitForm={paperExitForm}
          simulationResult={paperSimulationResult}
          exitResult={paperExitResult}
          exitEvaluationResult={paperExitEvaluationResult}
          performance={paperPerformance}
          performanceByStrategy={paperPerformanceByStrategy}
          performanceByDecision={paperPerformanceByDecision}
          performanceByRiskEvent={paperPerformanceByRiskEvent}
          performanceByWatchlist={paperPerformanceByWatchlist}
          performanceReport={paperPerformanceReport}
          loading={paperLoading}
          updatePortfolioField={updatePaperPortfolioField}
          updateSimulationField={updatePaperSimulationField}
          updateExitField={updatePaperExitField}
          onCreate={handlePaperPortfolioCreate}
          onDelete={handlePaperPortfolioDelete}
          onSelect={handlePaperPortfolioSelect}
          onSimulate={handlePaperSimulationSubmit}
          onSimulateExit={handlePaperPositionExit}
          onEvaluateExits={handlePaperEvaluateExits}
          onRefreshPerformance={handlePaperPerformanceRefresh}
          onCreatePerformanceReport={handlePaperPerformanceReport}
        />

        <WebhookPanel
          status={webhookStatus}
          events={webhookEvents}
          tradeReviews={tradeReviews}
          previewInput={webhookPreviewInput}
          setPreviewInput={setWebhookPreviewInput}
          previewProfile={webhookPreviewProfile}
          setPreviewProfile={setWebhookPreviewProfile}
          previewResult={webhookPreviewResult}
          previewLoading={webhookPreviewLoading}
          onPreview={handleWebhookPreview}
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

function OperationsDashboardPanel({
  summary,
  riskBrief,
  scheduleHealth,
  telegramStatus,
  webhookStatus,
  telegramResult,
  loading,
  diagnosticsSummary,
  diagnosticsSecurity,
  diagnosticsProviders,
  diagnosticsE2EStatus,
  onRefresh,
  onSendTelegram,
  onOpenMeeting
}) {
  const counts = summary?.counts || {};
  const riskSummary = summary?.risk_summary || {};
  const providerStatus = summary?.provider_status || {};
  const highRiskItems = riskBrief?.danger_items || [];
  const warningItems = riskBrief?.warning_items || [];
  const recentReviews = summary?.recent_watchlist_reviews || [];
  const recentRuns = scheduleHealth?.recent_runs || summary?.recent_schedule_runs || [];
  const paperSummary = summary?.paper_summary || {};
  return (
    <section className="tradeReviewSection" id="dashboard">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">Operations Dashboard</p>
          <h3>운영 대시보드</h3>
        </div>
        <div className="tradeReviewActions">
          <button className="secondaryButton" type="button" disabled={loading} onClick={onRefresh}>
            <RefreshCw size={17} aria-hidden="true" />
            운영 상태 새로고침
          </button>
          <button
            className="secondaryButton"
            type="button"
            disabled={loading}
            onClick={onSendTelegram}
          >
            <Send size={17} aria-hidden="true" />
            Risk Brief 보내기
          </button>
        </div>
      </div>
      <div className="dashboardGrid">
        <article>
          <span>시스템 상태</span>
          <strong>{summary?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>운영 요약 API 기준</p>
        </article>
        <article>
          <span>전체 시스템 진단</span>
          <strong>{diagnosticsSummary?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>One-click diagnostics 기준</p>
        </article>
        <article>
          <span>보안 점검 상태</span>
          <strong>{diagnosticsSecurity?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>Secret 노출 없음 · 주문 실행 비활성화</p>
        </article>
        <article>
          <span>Provider 점검 상태</span>
          <strong>{diagnosticsProviders?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>LLM/Market/Risk/Webhook/Telegram</p>
        </article>
        <article>
          <span>E2E script available</span>
          <strong>{diagnosticsE2EStatus?.full_e2e_script_available ? "사용 가능" : "확인 필요"}</strong>
          <p>{diagnosticsE2EStatus?.run_full_e2e_script_path || "scripts/run_full_e2e.sh"}</p>
        </article>
        <article>
          <span>전체 Watchlist 수</span>
          <strong>{counts.watchlists || 0}</strong>
          <p>등록된 관심종목 묶음</p>
        </article>
        <article>
          <span>최근 분석 수</span>
          <strong>{counts.watchlist_reviews || 0}</strong>
          <p>Watchlist Risk Brief 누적</p>
        </article>
        <article>
          <span>위험 종목 수</span>
          <strong>{riskSummary.block_count || riskBrief?.summary?.danger_count || 0}</strong>
          <p>BLOCK 또는 critical 중심</p>
        </article>
        <article>
          <span>주의 종목 수</span>
          <strong>{riskSummary.hold_count || riskBrief?.summary?.warning_count || 0}</strong>
          <p>HOLD 또는 high 중심</p>
        </article>
        <article>
          <span>추가 데이터 필요 수</span>
          <strong>{riskSummary.need_more_data_count || riskBrief?.summary?.need_more_data_count || 0}</strong>
          <p>NEED_MORE_DATA</p>
        </article>
        <article>
          <span>최근 실패한 스케줄 수</span>
          <strong>{scheduleHealth?.failed_run_count || 0}</strong>
          <p>Schedule run log 기준</p>
        </article>
        <article>
          <span>Telegram 비활성화 건수</span>
          <strong>{scheduleHealth?.telegram_disabled_count || 0}</strong>
          <p>자동 보고 disabled 기록</p>
        </article>
        <article>
          <span>현재 Market Data Provider</span>
          <strong>{providerStatus.market_data_provider || "mock_market_data"}</strong>
          <p>데이터 조회 전용</p>
        </article>
        <article>
          <span>현재 LLM Provider</span>
          <strong>{providerStatus.llm_provider || "mock"}</strong>
          <p>회의 생성 provider</p>
        </article>
        <article>
          <span>Telegram 상태</span>
          <strong>{telegramStatus?.configured ? "설정됨" : "비활성화"}</strong>
          <p>보고 전용</p>
        </article>
        <article>
          <span>Webhook 상태</span>
          <strong>{webhookStatus?.configured ? "수신 가능" : "비활성화"}</strong>
          <p>후보 신호 수신 전용</p>
        </article>
        <article>
          <span>Paper Portfolio 수</span>
          <strong>{counts.paper_portfolios || 0}</strong>
          <p>내부 가상 검증 전용</p>
        </article>
        <article>
          <span>최근 가상 거래 수</span>
          <strong>{paperSummary.recent_trade_count || 0}</strong>
          <p>실제 주문 없는 시뮬레이션 기록</p>
        </article>
        <article>
          <span>가상 노출 금액</span>
          <strong>{Number(paperSummary.virtual_exposure || 0).toFixed(2)}</strong>
          <p>Paper position 기준</p>
        </article>
        <article>
          <span>가상 손익</span>
          <strong>{Number(paperSummary.total_virtual_pnl || paperSummary.virtual_unrealized_pnl || 0).toFixed(2)}</strong>
          <p>평가 손익 + 실현 손익</p>
        </article>
        <article>
          <span>총 가상 평가금액</span>
          <strong>{Number(paperSummary.total_virtual_equity || 0).toFixed(2)}</strong>
          <p>현금 + 열린 가상 포지션</p>
        </article>
        <article>
          <span>열린 가상 포지션 수</span>
          <strong>{paperSummary.open_position_count || 0}</strong>
          <p>simulation_only 포지션</p>
        </article>
        <article>
          <span>최근 가상 청산 수</span>
          <strong>{paperSummary.recent_simulated_exit_count || 0}</strong>
          <p>simulated_exit 기록</p>
        </article>
        <article>
          <span>최근 성과 리포트 수</span>
          <strong>{counts.paper_performance_reports || 0}</strong>
          <p>가상 성과 리포트 누적</p>
        </article>
        <article>
          <span>가장 큰 가상 손실</span>
          <strong>{Number(paperSummary.largest_virtual_loss || 0).toFixed(2)}</strong>
          <p>simulated_exit realized PnL 기준</p>
        </article>
        <article className="safetyCard">
          <span>주문 실행 상태</span>
          <strong>비활성화</strong>
          <p>order_execution_allowed=false</p>
        </article>
      </div>

      <div className="autonomousGroups">
        <div className="autonomousGroup">
          <h4>최근 고위험 종목</h4>
          {highRiskItems.length > 0 ? (
            highRiskItems.slice(0, 6).map((item) => (
              <RiskBriefItem key={`${item.source_type}-${item.source_id}-${item.ticker}`} item={item} onOpenMeeting={onOpenMeeting} />
            ))
          ) : (
            <div className="emptyState">최근 고위험 종목이 없습니다.</div>
          )}
        </div>
        <div className="autonomousGroup">
          <h4>주의 종목</h4>
          {warningItems.length > 0 ? (
            warningItems.slice(0, 6).map((item) => (
              <RiskBriefItem key={`${item.source_type}-${item.source_id}-${item.ticker}`} item={item} onOpenMeeting={onOpenMeeting} />
            ))
          ) : (
            <div className="emptyState">최근 주의 종목이 없습니다.</div>
          )}
        </div>
      </div>

      <div className="webhookEvents">
        <h4>최근 Watchlist 분석</h4>
        {recentReviews.length > 0 ? (
          recentReviews.map((review) => (
            <article key={review.id}>
              <div>
                <strong>{review.watchlist_name || review.watchlist_id}</strong>
                <span>
                  {review.ticker_count || 0}개 · 최고 리스크 {riskLevelLabel(review.highest_risk_level)}
                </span>
              </div>
              <div>
                <span>위험/주의/추가데이터/허용</span>
                <strong>
                  {review.block_count || 0}/{review.hold_count || 0}/{review.need_more_data_count || 0}/
                  {review.allow_count || 0}
                </strong>
              </div>
              <div>
                <span>주문 실행 허용 여부</span>
                <strong>{booleanKo(Boolean(review.order_execution_allowed))}</strong>
              </div>
            </article>
          ))
        ) : (
          <div className="emptyState">최근 Watchlist 분석이 없습니다.</div>
        )}
      </div>

      <div className="webhookEvents">
        <h4>최근 스케줄 실행</h4>
        {recentRuns.length > 0 ? (
          recentRuns.map((run) => (
            <article key={run.id}>
              <div>
                <strong>{run.schedule_id?.slice(0, 8) || "schedule"}</strong>
                <span>{scheduleRunStatusLabel(run.status)} · {formatDateTime(run.finished_at)}</span>
              </div>
              <div>
                <span>Watchlist Review</span>
                <strong>{run.watchlist_review_id ? run.watchlist_review_id.slice(0, 8) : "없음"}</strong>
              </div>
              <div>
                <span>주문 실행 허용 여부</span>
                <strong>{booleanKo(Boolean(run.order_execution_allowed))}</strong>
              </div>
            </article>
          ))
        ) : (
          <div className="emptyState">최근 스케줄 실행 로그가 없습니다.</div>
        )}
      </div>

      <div className="webhookStatusGrid">
        <div>
          <span>활성 스케줄</span>
          <strong>{scheduleHealth?.enabled_schedules || 0}</strong>
        </div>
        <div>
          <span>비활성 스케줄</span>
          <strong>{scheduleHealth?.disabled_schedules || 0}</strong>
        </div>
        <div>
          <span>실행 대상 스케줄</span>
          <strong>{scheduleHealth?.due_schedules || 0}</strong>
        </div>
        <div>
          <span>마지막 실행 상태</span>
          <strong>{scheduleRunStatusLabel(scheduleHealth?.last_run_status)}</strong>
        </div>
      </div>

      {telegramResult && (
        <div className={`telegramResult ${telegramResult.sent ? "sent" : "disabled"}`}>
          <strong>{telegramResult.status}</strong>
          <p>{telegramResult.detail}</p>
        </div>
      )}
      <SafetyBoundary />
    </section>
  );
}

function DiagnosticsPanel({
  summary,
  security,
  providers,
  runtime,
  e2eStatus,
  loading,
  onRefresh
}) {
  const providerBlocks = providers?.providers || {};
  const configuredFlags = security?.configured_secret_flags || {};
  return (
    <section className="tradeReviewSection" id="diagnostics">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">One-click Operations Diagnostics</p>
          <h3>운영 진단</h3>
        </div>
        <button className="secondaryButton" type="button" disabled={loading} onClick={onRefresh}>
          <RefreshCw size={17} aria-hidden="true" />
          전체 진단 새로고침
        </button>
      </div>

      <div className="dashboardGrid">
        <article>
          <span>전체 상태</span>
          <strong>{summary?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>Backend health와 diagnostics summary 기준</p>
        </article>
        <article>
          <span>보안 점검</span>
          <strong>{security?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>Secret 노출 여부: {security?.secret_values_exposed ? "확인 필요" : "없음"}</p>
        </article>
        <article>
          <span>Provider 상태</span>
          <strong>{providers?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>각 provider 실패는 개별 항목에 표시됩니다.</p>
        </article>
        <article>
          <span>Runtime 정보</span>
          <strong>{runtime?.status === "ok" ? "정상" : "확인 필요"}</strong>
          <p>Python {runtime?.python_version || "확인 중"} · {runtime?.phase_label || "Phase 23 diagnostics"}</p>
        </article>
        <article>
          <span>E2E 점검 상태</span>
          <strong>{e2eStatus?.full_e2e_script_available ? "스크립트 사용 가능" : "확인 필요"}</strong>
          <p>{e2eStatus?.run_full_e2e_script_path || "scripts/run_full_e2e.sh"}</p>
        </article>
        <article className="safetyCard">
          <span>주문 실행 상태</span>
          <strong>비활성화</strong>
          <p>order_execution_allowed=false</p>
        </article>
        <article className="safetyCard">
          <span>브로커 연결 상태</span>
          <strong>{security?.broker_api_connected ? "확인 필요" : "연결 안 됨"}</strong>
          <p>진단은 read-only health check입니다.</p>
        </article>
        <article>
          <span>simulation_only</span>
          <strong>{summary?.safety?.simulation_only_confirmed ? "확인됨" : "확인 중"}</strong>
          <p>Paper Trading은 내부 가상 시뮬레이션 전용</p>
        </article>
      </div>

      <div className="webhookStatusGrid">
        <div>
          <span>LLM Provider</span>
          <strong>{providerBlocks.llm?.provider || summary?.providers?.llm_provider || "mock"}</strong>
        </div>
        <div>
          <span>Market Data Provider</span>
          <strong>{providerBlocks.market_data?.active_provider || summary?.providers?.market_data_provider || "mock_market_data"}</strong>
        </div>
        <div>
          <span>Risk Event Detector</span>
          <strong>{providerBlocks.risk_events?.detector_enabled ? "사용 가능" : "확인 필요"}</strong>
        </div>
        <div>
          <span>Telegram</span>
          <strong>{providerBlocks.telegram?.configured ? "설정됨" : "비활성화"}</strong>
        </div>
        <div>
          <span>Webhook</span>
          <strong>{providerBlocks.webhooks?.configured ? "수신 가능" : "비활성화"}</strong>
        </div>
        <div>
          <span>Database</span>
          <strong>{runtime?.database?.exists ? "확인됨" : "확인 필요"}</strong>
        </div>
        <div>
          <span>Reports directory</span>
          <strong>{runtime?.reports_directory_exists ? "있음" : "없음"}</strong>
        </div>
        <div>
          <span>E2E 예상 단계</span>
          <strong>{e2eStatus?.latest_e2e_expected_steps || 17}</strong>
        </div>
      </div>

      <div className="webhookEvents">
        <h4>Secret 설정 여부</h4>
        <article>
          <div>
            <strong>Secret 노출 여부: {security?.secret_values_exposed ? "확인 필요" : "없음"}</strong>
            <span>.env 내용은 진단 API에서 읽거나 반환하지 않습니다.</span>
          </div>
          <div>
            <span>Telegram token 설정</span>
            <strong>{configuredFlags.telegram_bot_token_configured ? "설정됨" : "미설정"}</strong>
          </div>
          <div>
            <span>Webhook secret 설정</span>
            <strong>{configuredFlags.webhook_secret_configured ? "설정됨" : "미설정"}</strong>
          </div>
          <div>
            <span>외부 데이터 API key 설정</span>
            <strong>{configuredFlags.market_data_api_key_configured ? "설정됨" : "미설정"}</strong>
          </div>
        </article>
      </div>

      <div className="telegramResult disabled">
        <strong>전체 시나리오 점검</strong>
        <p>
          E2E는 API에서 자동 실행하지 않습니다. 터미널에서 scripts/run_full_e2e.sh를 실행하세요.
          이 점검은 실제 주문을 실행하지 않습니다.
        </p>
      </div>

      <SafetyBoundary />
    </section>
  );
}

function RiskBriefItem({ item, onOpenMeeting }) {
  return (
    <article>
      <div>
        <strong>{item.ticker || "UNKNOWN"}</strong>
        <span>
          {decisionLabel(item.decision)} · {riskLevelLabel(item.risk_level)} · {item.source_type}
        </span>
        <span>
          리스크 이벤트 {item.top_risk_event || "없음"} · 데이터 품질 {dataQualityLabel(item.data_quality)}
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
  );
}

function DashboardCards({
  health,
  marketDataStatus,
  riskEventStatus,
  telegramStatus,
  webhookStatus,
  meetings,
  tradeReviews,
  watchlists,
  watchlistReviews,
  watchlistSchedules,
  watchlistScheduleRuns,
  paperPortfolios,
  operationsSummary
}) {
  const backendOk = health?.status === "ok";
  const llmProvider = health?.llm_provider || "mock";
  const marketDataProvider =
    marketDataStatus?.active_provider || health?.market_data?.provider || "mock_market_data";
  const latestWatchlistReview = watchlistReviews?.[0];
  const latestScheduleRun = watchlistScheduleRuns?.[0];
  const paperSummary = operationsSummary?.paper_summary || {};
  return (
    <section className="dashboardGrid" id="dashboard-cards">
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
        <span>뉴스/공시 리스크</span>
        <strong>{riskEventStatus?.risk_event_detector || "risk_event_detector"}</strong>
        <p>뉴스 {riskEventStatus?.active_news_provider || "mock_news_provider"} · 공시 {riskEventStatus?.active_sec_filing_provider || "mock_sec_filing_provider"}</p>
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
      <article>
        <span>Watchlist 수</span>
        <strong>{watchlists.length}</strong>
        <p>관심종목 묶음</p>
      </article>
      <article>
        <span>최근 Watchlist 분석 수</span>
        <strong>{watchlistReviews.length}</strong>
        <p>Batch review 기록</p>
      </article>
      <article>
        <span>가상 검증 포트폴리오</span>
        <strong>{paperPortfolios.length}</strong>
        <p>Paper Trading은 내부 시뮬레이션 전용</p>
      </article>
      <article>
        <span>가상 노출/손익</span>
        <strong>{Number(paperSummary.virtual_exposure || 0).toFixed(2)}</strong>
        <p>총 손익 {Number(paperSummary.total_virtual_pnl || paperSummary.virtual_unrealized_pnl || 0).toFixed(2)}</p>
      </article>
      <article>
        <span>가상 청산/포지션</span>
        <strong>{paperSummary.recent_simulated_exit_count || 0}</strong>
        <p>열린 포지션 {paperSummary.open_position_count || 0} · simulation_only</p>
      </article>
      <article>
        <span>가상 성과 리포트</span>
        <strong>{operationsSummary?.counts?.paper_performance_reports || 0}</strong>
        <p>가장 큰 가상 손실 {Number(paperSummary.largest_virtual_loss || 0).toFixed(2)}</p>
      </article>
      <article>
        <span>자동 분석 스케줄 수</span>
        <strong>{watchlistSchedules.length}</strong>
        <p>run-due로 호출 가능한 분석/보고 일정</p>
      </article>
      <article>
        <span>최근 스케줄 실행</span>
        <strong>{latestScheduleRun ? scheduleRunStatusLabel(latestScheduleRun.status) : "없음"}</strong>
        <p>{latestScheduleRun ? formatDateTime(latestScheduleRun.finished_at) : "실행 로그 없음"}</p>
      </article>
      <article>
        <span>최근 위험 종목 수</span>
        <strong>{latestWatchlistReview?.blocked_count || 0}</strong>
        <p>BLOCK 또는 critical 후보 중심</p>
      </article>
      <article>
        <span>최고 리스크 수준</span>
        <strong>{latestWatchlistReview?.highest_risk_level || "없음"}</strong>
        <p>최근 Watchlist 분석 기준</p>
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
          <dt>전체 시나리오 점검</dt>
          <dd>Watchlist부터 가상 성과 리포트까지 전체 흐름을 확인합니다. 터미널에서 scripts/run_full_e2e.sh를 실행하세요. 이 점검은 실제 주문을 실행하지 않습니다.</dd>
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

function RiskEventPanel({ status, ticker, setTicker, result, loading, onLookup }) {
  const events = result?.payload?.events || [];
  const topEvent = result?.payload?.top_event;
  return (
    <section className="tradeReviewSection" id="risk-events">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">Phase 14 News, SEC Filing & Risk Event Provider</p>
          <h3>뉴스/공시 리스크</h3>
        </div>
        <span>주문 실행 허용 여부: false</span>
      </div>
      <div className="webhookStatusGrid">
        <div>
          <span>뉴스 Provider</span>
          <strong>{status?.active_news_provider || "mock_news_provider"}</strong>
        </div>
        <div>
          <span>공시 Provider</span>
          <strong>{status?.active_sec_filing_provider || "mock_sec_filing_provider"}</strong>
        </div>
        <div>
          <span>Detector</span>
          <strong>{status?.detector_enabled ? "켜짐" : "꺼짐"}</strong>
        </div>
        <div>
          <span>외부 뉴스 사용 여부</span>
          <strong>{booleanKo(Boolean(status?.news_external_enabled))}</strong>
        </div>
        <div>
          <span>외부 공시 사용 여부</span>
          <strong>{booleanKo(Boolean(status?.sec_external_enabled))}</strong>
        </div>
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(status?.order_execution_allowed))}</strong>
        </div>
      </div>
      <form className="marketDataLookup" onSubmit={(event) => event.preventDefault()}>
        <label>
          <span>티커</span>
          <input
            value={ticker}
            onChange={(event) => setTicker(event.target.value)}
            placeholder="TESTB"
            maxLength={16}
          />
        </label>
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
        <button
          className="secondaryButton"
          type="button"
          disabled={loading || !ticker.trim()}
          onClick={() => onLookup("detect")}
        >
          리스크 이벤트 감지
        </button>
      </form>
      <p className="contextHint">
        뉴스와 공시 텍스트를 읽기 전용으로 분류합니다. 이 기능은 주문을 실행하지 않습니다.
      </p>
      {result && (
        <div className="jsonResult">
          <div className="panelHeading">
            <h3>{result.kind} 결과</h3>
            <span>{booleanKo(Boolean(result.payload?.order_execution_allowed))}</span>
          </div>
          {topEvent && (
            <div className="decisionMetrics compactMetrics">
              <div>
                <span>Top 이벤트</span>
                <strong>{topEvent.event_type}</strong>
              </div>
              <div>
                <span>심각도</span>
                <strong>{riskLevelLabel(topEvent.severity)}</strong>
              </div>
              <div>
                <span>판단 영향</span>
                <strong>{topEvent.recommended_decision_impact}</strong>
              </div>
            </div>
          )}
          {events.length > 0 && (
            <div className="autonomousGroups">
              <div className="autonomousGroup">
                <h4>감지된 이벤트</h4>
                {events.map((event) => (
                  <article key={`${event.event_type}-${event.severity}`}>
                    <div>
                      <strong>{event.event_type}</strong>
                      <span>
                        심각도 {riskLevelLabel(event.severity)} · 판단 영향 {event.recommended_decision_impact}
                      </span>
                      <span>근거: {(event.evidence || []).slice(0, 2).join("; ") || "없음"}</span>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          )}
          <pre>{JSON.stringify(result.payload, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}

function WatchlistPanel({
  watchlists,
  selectedWatchlistId,
  setSelectedWatchlistId,
  form,
  updateField,
  loading,
  result,
  telegramResult,
  telegramConfigured,
  onCreate,
  onDelete,
  onRun,
  onSendTelegram,
  onOpenMeeting
}) {
  const selectedWatchlist = watchlists.find((item) => item.id === selectedWatchlistId);
  return (
    <section className="tradeReviewSection" id="watchlists">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">Phase 15 Watchlist Batch Review</p>
          <h3>관심종목 Watchlist</h3>
        </div>
        <span>주문 실행 허용 여부: false</span>
      </div>
      <form className="tickerReviewForm" onSubmit={onCreate}>
        <label>
          <span>Watchlist 이름</span>
          <input
            value={form.name}
            onChange={(event) => updateField("name", event.target.value)}
            placeholder="Penny Stock Watchlist"
          />
        </label>
        <label>
          <span>분석 모드</span>
          <select value={form.review_mode} onChange={(event) => updateField("review_mode", event.target.value)}>
            <option value="penny_stock_risk">페니주 리스크 검토 (penny_stock_risk)</option>
            <option value="momentum_review">모멘텀 검토 (momentum_review)</option>
            <option value="long_term_review">장기 관점 검토 (long_term_review)</option>
            <option value="news_catalyst_review">뉴스 촉매 검토 (news_catalyst_review)</option>
            <option value="general_review">일반 검토 (general_review)</option>
          </select>
        </label>
        <label className="wideField">
          <span>설명</span>
          <input
            value={form.description}
            onChange={(event) => updateField("description", event.target.value)}
            placeholder="관심 penny stock 후보군"
          />
        </label>
        <label className="wideField">
          <span>종목 목록</span>
          <textarea
            value={form.tickers}
            onChange={(event) => updateField("tickers", event.target.value)}
            rows={5}
            placeholder={"TESTA\nTESTB\nTESTC"}
          />
        </label>
        <button className="primaryButton" type="submit" disabled={loading || !form.name.trim()}>
          <Plus size={18} aria-hidden="true" />
          새 Watchlist 만들기
        </button>
      </form>
      <p className="contextHint">
        관심종목을 한 번에 Risk Gate Review로 검토합니다. ALLOW는 검토상 허용일 뿐 실제 매수 허용이 아닙니다.
      </p>
      <div className="recentTradeReviews">
        <h4>Watchlist 목록</h4>
        <div>
          {watchlists.map((watchlist) => (
            <button
              type="button"
              key={watchlist.id}
              className={selectedWatchlistId === watchlist.id ? "active" : ""}
              onClick={() => setSelectedWatchlistId(watchlist.id)}
            >
              <strong>{watchlist.name}</strong>
              <span>
                {watchlist.ticker_count}개 · {watchlist.review_mode}
              </span>
            </button>
          ))}
          {watchlists.length === 0 && <div className="emptyState">아직 Watchlist가 없습니다.</div>}
        </div>
      </div>
      {selectedWatchlist && (
        <div className="tradeReviewResultCard">
          <div className="decisionHeader">
            <div>
              <p className="eyebrow">Watchlist 상세</p>
              <h3>{selectedWatchlist.name}</h3>
            </div>
            <div className="badgeGroup">
              <span className="decisionBadge hold">{selectedWatchlist.ticker_count}개</span>
              <span className="riskBadge medium">주문 없음</span>
            </div>
          </div>
          <div className="decisionMetrics">
            <div>
              <span>분석 모드</span>
              <strong>{selectedWatchlist.review_mode}</strong>
            </div>
            <div>
              <span>종목</span>
              <strong>{selectedWatchlist.tickers.join(", ")}</strong>
            </div>
            <div>
              <span>주문 실행 허용 여부</span>
              <strong>{booleanKo(Boolean(selectedWatchlist.order_execution_allowed))}</strong>
            </div>
          </div>
          <div className="tradeReviewActions">
            <button className="primaryButton" type="button" disabled={loading} onClick={() => onRun(selectedWatchlist.id)}>
              <Shield size={18} aria-hidden="true" />
              Watchlist 분석 실행
            </button>
            <button className="secondaryButton" type="button" disabled={loading} onClick={() => onDelete(selectedWatchlist.id)}>
              <Trash2 size={17} aria-hidden="true" />
              삭제
            </button>
          </div>
        </div>
      )}
      {result && (
        <WatchlistReviewResult
          result={result}
          telegramResult={telegramResult}
          telegramConfigured={telegramConfigured}
          loading={loading}
          onSendTelegram={onSendTelegram}
          onOpenMeeting={onOpenMeeting}
        />
      )}
    </section>
  );
}

function WatchlistReviewResult({
  result,
  telegramResult,
  telegramConfigured,
  loading,
  onSendTelegram,
  onOpenMeeting
}) {
  const summary = result.summary || {};
  const groups = [
    ["위험 종목", result.results?.filter((item) => item.decision === "BLOCK" || item.risk_level === "critical") || []],
    ["주의 종목", result.results?.filter((item) => item.decision === "HOLD" || item.risk_level === "high") || []],
    ["추가 데이터 필요", result.results?.filter((item) => item.decision === "NEED_MORE_DATA") || []],
    ["검토상 허용", result.results?.filter((item) => item.decision === "ALLOW") || []]
  ];
  return (
    <section className="tradeReviewResultCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">Watchlist Risk Brief</p>
          <h3>
            {result.watchlist_name} · {result.ticker_count}개 분석
          </h3>
        </div>
        <div className="badgeGroup">
          <span className="decisionBadge hold">HOLD {summary.hold_count || 0}</span>
          <span className="riskBadge critical">BLOCK {summary.block_count || 0}</span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>위험 종목</span>
          <strong>{summary.block_count || 0}</strong>
        </div>
        <div>
          <span>주의 종목</span>
          <strong>{summary.hold_count || 0}</strong>
        </div>
        <div>
          <span>추가 데이터 필요</span>
          <strong>{summary.need_more_data_count || 0}</strong>
        </div>
        <div>
          <span>검토상 허용</span>
          <strong>{summary.allow_count || 0}</strong>
        </div>
        <div>
          <span>최고 리스크 수준</span>
          <strong>{riskLevelLabel(summary.highest_risk_level || result.highest_risk_level)}</strong>
        </div>
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(result.order_execution_allowed))}</strong>
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
                      {decisionLabel(item.decision)} · {riskLevelLabel(item.risk_level)}
                    </span>
                    <span>
                      리스크 이벤트 {item.top_risk_event || "없음"} · {item.risk_event_severity ? riskLevelLabel(item.risk_event_severity) : "없음"}
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
              <div className="emptyState">해당 종목이 없습니다.</div>
            )}
          </div>
        ))}
      </div>
      <div className="tradeReviewActions">
        <button
          className="secondaryButton"
          type="button"
          disabled={loading || !telegramConfigured}
          onClick={onSendTelegram}
        >
          <Send size={17} aria-hidden="true" />
          텔레그램으로 보내기
        </button>
        {result.report?.path && (
          <span className="contextHint">Report: {result.report.path}</span>
        )}
      </div>
      {telegramResult && (
        <div className={`telegramResult ${telegramResult.sent ? "sent" : "disabled"}`}>
          <strong>{telegramResult.status}</strong>
          <p>{telegramResult.detail}</p>
        </div>
      )}
      <p className="contextHint">
        이 기능은 주문을 실행하지 않습니다. 모든 결과의 order_execution_allowed는 false입니다.
      </p>
    </section>
  );
}

function WatchlistSchedulePanel({
  watchlists,
  schedules,
  runs,
  form,
  updateField,
  loading,
  result,
  telegramConfigured,
  onCreate,
  onDelete,
  onRunNow,
  onRunDue,
  onOpenMeeting
}) {
  const watchlistById = new Map(watchlists.map((watchlist) => [watchlist.id, watchlist]));
  const scheduleById = new Map(schedules.map((schedule) => [schedule.id, schedule]));
  return (
    <section className="tradeReviewSection" id="watchlist-schedules">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">Phase 16 Scheduled Watchlist Review</p>
          <h3>자동 분석 스케줄</h3>
        </div>
        <button className="secondaryButton" type="button" disabled={loading} onClick={onRunDue}>
          <RefreshCw size={17} aria-hidden="true" />
          실행 대상 스케줄 실행
        </button>
      </div>
      <form className="tickerReviewForm" onSubmit={onCreate}>
        <label>
          <span>연결된 Watchlist</span>
          <select
            value={form.watchlist_id}
            onChange={(event) => updateField("watchlist_id", event.target.value)}
          >
            <option value="">Watchlist 선택</option>
            {watchlists.map((watchlist) => (
              <option value={watchlist.id} key={watchlist.id}>
                {watchlist.name} ({watchlist.ticker_count}개)
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>스케줄 이름</span>
          <input
            value={form.name}
            onChange={(event) => updateField("name", event.target.value)}
            placeholder="매일 장전 리스크 점검"
          />
        </label>
        <label>
          <span>실행 주기</span>
          <select value={form.cadence} onChange={(event) => updateField("cadence", event.target.value)}>
            <option value="manual_only">수동 실행 전용 (manual_only)</option>
            <option value="daily">매일 (daily)</option>
            <option value="weekdays">평일 (weekdays)</option>
            <option value="hourly_stub">1시간마다 stub (hourly_stub)</option>
            <option value="market_open_stub">장 시작 전 stub (market_open_stub)</option>
            <option value="market_close_stub">장 마감 후 stub (market_close_stub)</option>
          </select>
        </label>
        <label>
          <span>실행 시간</span>
          <input
            value={form.run_time}
            onChange={(event) => updateField("run_time", event.target.value)}
            placeholder="08:30"
            maxLength={5}
          />
        </label>
        <label>
          <span>시간대</span>
          <input
            value={form.timezone}
            onChange={(event) => updateField("timezone", event.target.value)}
            placeholder="Asia/Seoul"
          />
        </label>
        <label className="checkboxLabel">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(event) => updateField("enabled", event.target.checked)}
          />
          <span>활성화</span>
        </label>
        <label className="checkboxLabel">
          <input
            type="checkbox"
            checked={form.auto_send_telegram}
            onChange={(event) => updateField("auto_send_telegram", event.target.checked)}
          />
          <span>텔레그램 자동 보고</span>
        </label>
        <button
          className="primaryButton"
          type="submit"
          disabled={loading || !form.watchlist_id || !form.name.trim()}
        >
          <Plus size={18} aria-hidden="true" />
          새 스케줄 만들기
        </button>
      </form>
      <p className="contextHint">
        자동 스케줄은 Watchlist 분석과 보고만 수행합니다. 이 기능은 주문을 실행하지 않습니다.
        텔레그램 자동 보고는 설정이 없으면 disabled로 기록됩니다.
      </p>
      <div className="webhookStatusGrid">
        <div>
          <span>스케줄 수</span>
          <strong>{schedules.length}</strong>
        </div>
        <div>
          <span>활성 스케줄</span>
          <strong>{schedules.filter((schedule) => schedule.enabled).length}</strong>
        </div>
        <div>
          <span>최근 실행 로그</span>
          <strong>{runs.length}</strong>
        </div>
        <div>
          <span>Telegram 설정</span>
          <strong>{telegramConfigured ? "설정됨" : "비활성화"}</strong>
        </div>
      </div>

      <div className="autonomousGroups">
        <div className="autonomousGroup">
          <h4>스케줄 목록</h4>
          {schedules.length > 0 ? (
            schedules.map((schedule) => {
              const watchlist = watchlistById.get(schedule.watchlist_id);
              return (
                <article key={schedule.id}>
                  <div>
                    <strong>{schedule.name}</strong>
                    <span>
                      {watchlist?.name || schedule.watchlist_id} · {scheduleCadenceLabel(schedule.cadence)}
                    </span>
                    <span>
                      다음 실행 시각: {formatDateTime(schedule.next_run_at)} · 마지막 실행 시각:{" "}
                      {formatDateTime(schedule.last_run_at)}
                    </span>
                    <span>
                      활성화 {booleanKo(Boolean(schedule.enabled))} · 텔레그램 자동 보고{" "}
                      {booleanKo(Boolean(schedule.auto_send_telegram))} · 주문 실행 허용 여부{" "}
                      {booleanKo(Boolean(schedule.order_execution_allowed))}
                    </span>
                  </div>
                  <div className="tradeReviewActions">
                    <button
                      className="secondaryButton"
                      type="button"
                      disabled={loading}
                      onClick={() => onRunNow(schedule.id)}
                    >
                      <Play size={16} aria-hidden="true" />
                      지금 실행
                    </button>
                    <button
                      className="secondaryButton"
                      type="button"
                      disabled={loading}
                      onClick={() => onDelete(schedule.id)}
                    >
                      <Trash2 size={16} aria-hidden="true" />
                      삭제
                    </button>
                  </div>
                </article>
              );
            })
          ) : (
            <div className="emptyState">아직 자동 분석 스케줄이 없습니다.</div>
          )}
        </div>
      </div>

      {result && <ScheduleRunResult result={result} onOpenMeeting={onOpenMeeting} />}

      <div className="webhookEvents">
        <h4>최근 실행 로그</h4>
        {runs.length > 0 ? (
          runs.slice(0, 6).map((run) => {
            const schedule = scheduleById.get(run.schedule_id);
            return (
              <article key={run.id}>
                <div>
                  <strong>{schedule?.name || run.schedule_id.slice(0, 8)}</strong>
                  <span>
                    {scheduleRunStatusLabel(run.status)} · {formatDateTime(run.finished_at)}
                  </span>
                </div>
                <div>
                  <span>Watchlist Review</span>
                  <strong>{run.watchlist_review_id ? run.watchlist_review_id.slice(0, 8) : "없음"}</strong>
                </div>
                <div>
                  <span>주문 실행 허용 여부</span>
                  <strong>{booleanKo(Boolean(run.order_execution_allowed))}</strong>
                </div>
              </article>
            );
          })
        ) : (
          <div className="emptyState">아직 schedule run log가 없습니다.</div>
        )}
      </div>
    </section>
  );
}

function ScheduleRunResult({ result, onOpenMeeting }) {
  const isRunDue = Array.isArray(result.results);
  const runs = isRunDue ? result.results : [result];
  return (
    <section className="tradeReviewResultCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">스케줄 실행 결과</p>
          <h3>{isRunDue ? "실행 대상 스케줄 처리" : result.schedule?.name || "지금 실행"}</h3>
        </div>
        <div className="badgeGroup">
          <span className="decisionBadge hold">
            실행 {isRunDue ? result.executed_count : 1}
          </span>
          <span className="riskBadge medium">
            실패 {isRunDue ? result.failed_count : result.run?.status === "failed" ? 1 : 0}
          </span>
        </div>
      </div>
      <div className="decisionMetrics">
        {isRunDue ? (
          <>
            <div>
              <span>실행 대상</span>
              <strong>{result.due_count}</strong>
            </div>
            <div>
              <span>실행 완료</span>
              <strong>{result.executed_count}</strong>
            </div>
            <div>
              <span>실패</span>
              <strong>{result.failed_count}</strong>
            </div>
            <div>
              <span>건너뜀</span>
              <strong>{result.skipped_count}</strong>
            </div>
          </>
        ) : (
          <>
            <div>
              <span>실행 상태</span>
              <strong>{scheduleRunStatusLabel(result.run?.status)}</strong>
            </div>
            <div>
              <span>분석 종목 수</span>
              <strong>{result.review?.ticker_count || 0}</strong>
            </div>
            <div>
              <span>최고 리스크 수준</span>
              <strong>{riskLevelLabel(result.review?.highest_risk_level)}</strong>
            </div>
            <div>
              <span>Telegram 상태</span>
              <strong>{result.telegram?.status || "not_requested"}</strong>
            </div>
          </>
        )}
        <div>
          <span>주문 실행 허용 여부</span>
          <strong>{booleanKo(Boolean(result.order_execution_allowed))}</strong>
        </div>
      </div>
      <div className="autonomousGroups">
        {runs.map((item) => {
          const review = item.review || {};
          const firstMeetingId = review.results?.[0]?.linked_meeting_id;
          return (
            <div className="autonomousGroup" key={item.run?.id || item.schedule?.id || "run-due"}>
              <h4>{item.schedule?.name || item.schedule?.id || "실행 결과"}</h4>
              <article>
                <div>
                  <strong>{review.watchlist_name || "Watchlist Risk Brief"}</strong>
                  <span>
                    {review.ticker_count || 0}개 분석 · 최고 리스크{" "}
                    {riskLevelLabel(review.highest_risk_level)}
                  </span>
                  <span>
                    Telegram: {item.telegram?.status || "not_requested"} · 주문 실행 허용 여부{" "}
                    {booleanKo(Boolean(item.order_execution_allowed))}
                  </span>
                </div>
                <button
                  className="secondaryButton"
                  type="button"
                  disabled={!firstMeetingId}
                  onClick={() => firstMeetingId && onOpenMeeting(firstMeetingId)}
                >
                  <FileText size={16} aria-hidden="true" />
                  첫 회의 열기
                </button>
              </article>
            </div>
          );
        })}
      </div>
      {isRunDue && result.errors?.length > 0 && (
        <div className="telegramResult disabled">
          <strong>일부 스케줄 실패</strong>
          <p>{result.errors.map((error) => `${error.schedule_id}: ${error.error}`).join(" / ")}</p>
        </div>
      )}
      <p className="contextHint">
        이 기능은 자동 분석/자동 보고 전용입니다. 자동 주문 또는 자동 매매 기능이 아닙니다.
      </p>
    </section>
  );
}

function PaperTradingPanel({
  portfolios,
  selectedPortfolioId,
  detail,
  portfolioForm,
  simulationForm,
  exitForm,
  simulationResult,
  exitResult,
  exitEvaluationResult,
  performance,
  performanceByStrategy,
  performanceByDecision,
  performanceByRiskEvent,
  performanceByWatchlist,
  performanceReport,
  loading,
  updatePortfolioField,
  updateSimulationField,
  updateExitField,
  onCreate,
  onDelete,
  onSelect,
  onSimulate,
  onSimulateExit,
  onEvaluateExits,
  onRefreshPerformance,
  onCreatePerformanceReport
}) {
  const summary = detail?.summary || {};
  const positions = detail?.positions || [];
  const trades = detail?.trades || [];
  const strategyGroups = performanceByStrategy?.groups || [];
  const decisionGroups = performanceByDecision?.groups || [];
  const riskEventGroups = performanceByRiskEvent?.groups || [];
  const watchlistGroups = performanceByWatchlist?.groups || [];
  return (
    <section className="tradeReviewSection" id="paper-trading">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">Paper Trading Simulation Mode</p>
          <h3>가상 검증 / Paper Trading 시뮬레이션</h3>
        </div>
        <span>실제 주문 없음</span>
      </div>
      <p className="contextHint">
        Trade Review, Ticker Review, Watchlist Review, Webhook 결과를 내부 가상 포트폴리오에만 반영합니다.
        브로커 계좌나 실제 주문 API와 연결하지 않습니다.
        이 기능은 내부 시뮬레이션 전용입니다.
      </p>

      <form className="tickerReviewForm" onSubmit={onCreate}>
        <label>
          <span>새 가상 포트폴리오</span>
          <input
            value={portfolioForm.name}
            onChange={(event) => updatePortfolioField("name", event.target.value)}
          />
        </label>
        <label>
          <span>시작 현금</span>
          <input
            type="number"
            min="1"
            value={portfolioForm.starting_cash}
            onChange={(event) => updatePortfolioField("starting_cash", event.target.value)}
          />
        </label>
        <label className="wideField">
          <span>설명</span>
          <input
            value={portfolioForm.description}
            onChange={(event) => updatePortfolioField("description", event.target.value)}
          />
        </label>
        <div className="tradeReviewActions">
          <button className="primaryButton" type="submit" disabled={loading || !portfolioForm.name.trim()}>
            <Plus size={16} aria-hidden="true" />
            포트폴리오 생성
          </button>
        </div>
      </form>

      <div className="webhookEvents">
        <h4>포트폴리오 목록</h4>
        {portfolios.length > 0 ? (
          portfolios.map((portfolio) => (
            <article key={portfolio.id}>
              <div>
                <strong>{portfolio.name}</strong>
                <span>
                  현금 {Number(portfolio.cash_balance || 0).toFixed(2)} / 시작{" "}
                  {Number(portfolio.starting_cash || 0).toFixed(2)}
                </span>
              </div>
              <div>
                <span>주문 실행 허용 여부</span>
                <strong>{booleanKo(Boolean(portfolio.order_execution_allowed))}</strong>
              </div>
              <div className="tradeReviewActions">
                <button
                  className="secondaryButton"
                  type="button"
                  disabled={selectedPortfolioId === portfolio.id}
                  onClick={() => onSelect(portfolio.id)}
                >
                  선택
                </button>
                <button
                  className="iconButton"
                  type="button"
                  title="가상 포트폴리오 삭제"
                  onClick={() => onDelete(portfolio.id)}
                  disabled={loading}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className="emptyState">아직 가상 포트폴리오가 없습니다.</div>
        )}
      </div>

      {detail && (
        <>
          <div className="webhookStatusGrid">
            <div>
              <span>현금</span>
              <strong>{Number(summary.cash_balance || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span>포지션 수</span>
              <strong>{summary.position_count || 0}</strong>
            </div>
            <div>
              <span>가상 노출</span>
              <strong>{Number(summary.exposure || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span>평가 손익</span>
              <strong>{Number(summary.unrealized_pnl || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span>실현 손익</span>
              <strong>{Number(summary.realized_pnl || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span>총 가상 손익</span>
              <strong>{Number(summary.total_pnl || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span>총 가상 평가금액</span>
              <strong>{Number(summary.total_equity || 0).toFixed(2)}</strong>
            </div>
            <div>
              <span>노출 비중</span>
              <strong>{Number(summary.exposure_pct || 0).toFixed(2)}%</strong>
            </div>
            <div>
              <span>시뮬레이션 전용</span>
              <strong>{summary.paper_trade_execution_allowed || "simulation_only"}</strong>
            </div>
            <div>
              <span>주문 실행 허용 여부</span>
              <strong>{booleanKo(Boolean(summary.order_execution_allowed))}</strong>
            </div>
          </div>

          <form className="tickerReviewForm" onSubmit={onSimulate}>
            <label>
              <span>Source type</span>
              <select
                value={simulationForm.source_type}
                onChange={(event) => updateSimulationField("source_type", event.target.value)}
              >
                <option value="trade_review">trade_review</option>
                <option value="ticker_review">ticker_review</option>
                <option value="autonomous_review">autonomous_review</option>
                <option value="watchlist_review">watchlist_review</option>
                <option value="webhook_event">webhook_event</option>
              </select>
            </label>
            <label>
              <span>Source review id</span>
              <input
                value={simulationForm.source_id}
                onChange={(event) => updateSimulationField("source_id", event.target.value)}
                placeholder="검토 결과 ID"
              />
            </label>
            <label>
              <span>시뮬레이션 정책</span>
              <select
                value={simulationForm.simulation_policy}
                onChange={(event) => updateSimulationField("simulation_policy", event.target.value)}
              >
                <option value="risk_gate_conservative">risk_gate_conservative</option>
                <option value="observe_only">observe_only</option>
                <option value="aggressive_research_only">aggressive_research_only</option>
              </select>
            </label>
            <label>
              <span>최대 가상 금액</span>
              <input
                type="number"
                min="1"
                value={simulationForm.max_notional_per_trade}
                onChange={(event) => updateSimulationField("max_notional_per_trade", event.target.value)}
              />
            </label>
            <label>
              <span>슬리피지 bps</span>
              <input
                type="number"
                min="0"
                value={simulationForm.slippage_bps}
                onChange={(event) => updateSimulationField("slippage_bps", event.target.value)}
              />
            </label>
            <label>
              <span>스프레드 bps</span>
              <input
                type="number"
                min="0"
                value={simulationForm.spread_bps}
                onChange={(event) => updateSimulationField("spread_bps", event.target.value)}
              />
            </label>
            <label>
              <span>최대 스프레드 %</span>
              <input
                type="number"
                min="0"
                step="0.1"
                value={simulationForm.max_spread_pct}
                onChange={(event) => updateSimulationField("max_spread_pct", event.target.value)}
              />
            </label>
            <label>
              <span>가상 익절 %</span>
              <input
                type="number"
                min="0.1"
                step="0.1"
                value={simulationForm.take_profit_pct}
                onChange={(event) => updateSimulationField("take_profit_pct", event.target.value)}
              />
            </label>
            <label>
              <span>가상 손절 %</span>
              <input
                type="number"
                min="0.1"
                step="0.1"
                value={simulationForm.stop_loss_pct}
                onChange={(event) => updateSimulationField("stop_loss_pct", event.target.value)}
              />
            </label>
            <label className="checkboxLabel">
              <input
                type="checkbox"
                checked={simulationForm.allow_only_decision}
                onChange={(event) => updateSimulationField("allow_only_decision", event.target.checked)}
              />
              <span>ALLOW만 반영</span>
            </label>
            <div className="tradeReviewActions">
              <button className="primaryButton" type="submit" disabled={loading || !simulationForm.source_id.trim()}>
                <Play size={16} aria-hidden="true" />
                검토 결과를 가상 포트폴리오에 반영
              </button>
            </div>
          </form>

          {simulationResult && (
            <div className="jsonResult">
              <div className="webhookStatusGrid">
                <div>
                  <span>생성된 기록</span>
                  <strong>{simulationResult.trades?.length || 0}</strong>
                </div>
                <div>
                  <span>시뮬레이션 전용</span>
                  <strong>{simulationResult.paper_trade_execution_allowed}</strong>
                </div>
                <div>
                  <span>주문 실행 허용 여부</span>
                  <strong>{booleanKo(Boolean(simulationResult.order_execution_allowed))}</strong>
                </div>
              </div>
              <pre>{JSON.stringify(simulationResult.trades || simulationResult, null, 2)}</pre>
            </div>
          )}

          <div className="webhookEvents">
            <h4>청산 조건 평가</h4>
            <div className="tickerReviewForm">
              <label>
                <span>가상 청산 사유</span>
                <select
                  value={exitForm.exit_reason}
                  onChange={(event) => updateExitField("exit_reason", event.target.value)}
                >
                  <option value="manual_simulated_exit">manual_simulated_exit</option>
                  <option value="simulated_take_profit">simulated_take_profit</option>
                  <option value="simulated_stop_loss">simulated_stop_loss</option>
                  <option value="simulated_risk_exit">simulated_risk_exit</option>
                  <option value="simulated_data_quality_exit">simulated_data_quality_exit</option>
                </select>
              </label>
              <label>
                <span>가상 청산 가격</span>
                <input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={exitForm.exit_price}
                  onChange={(event) => updateExitField("exit_price", event.target.value)}
                  placeholder="비우면 provider 가격 사용"
                />
              </label>
              <label>
                <span>청산 슬리피지 bps</span>
                <input
                  type="number"
                  min="0"
                  value={exitForm.slippage_bps}
                  onChange={(event) => updateExitField("slippage_bps", event.target.value)}
                />
              </label>
              <label>
                <span>청산 스프레드 bps</span>
                <input
                  type="number"
                  min="0"
                  value={exitForm.spread_bps}
                  onChange={(event) => updateExitField("spread_bps", event.target.value)}
                />
              </label>
              <div className="tradeReviewActions">
                <button className="secondaryButton" type="button" disabled={loading} onClick={() => onEvaluateExits(false)}>
                  <RefreshCw size={16} aria-hidden="true" />
                  청산 조건 평가
                </button>
                <button className="secondaryButton" type="button" disabled={loading} onClick={() => onEvaluateExits(true)}>
                  <Play size={16} aria-hidden="true" />
                  조건 충족 시 가상 청산 기록
                </button>
              </div>
            </div>
            <p className="contextHint">
              가상 손절/가상 익절 조건만 평가합니다. 실제 주문 없음, 내부 시뮬레이션 전용입니다.
            </p>
          </div>

          {exitEvaluationResult && (
            <div className="jsonResult">
              <div className="webhookStatusGrid">
                <div>
                  <span>청산 후보</span>
                  <strong>{exitEvaluationResult.exit_candidates?.length || 0}</strong>
                </div>
                <div>
                  <span>가상 청산 기록</span>
                  <strong>{exitEvaluationResult.executed_exits?.length || 0}</strong>
                </div>
                <div>
                  <span>주문 실행 허용 여부</span>
                  <strong>{booleanKo(Boolean(exitEvaluationResult.order_execution_allowed))}</strong>
                </div>
              </div>
              <pre>{JSON.stringify(exitEvaluationResult, null, 2)}</pre>
            </div>
          )}

          {exitResult && (
            <div className="jsonResult">
              <div className="webhookStatusGrid">
                <div>
                  <span>가상 청산 가격</span>
                  <strong>{Number(exitResult.simulated_exit_price || 0).toFixed(4)}</strong>
                </div>
                <div>
                  <span>실현 손익</span>
                  <strong>{Number(exitResult.realized_pnl || 0).toFixed(2)}</strong>
                </div>
                <div>
                  <span>시뮬레이션 전용</span>
                  <strong>{exitResult.paper_trade_execution_allowed}</strong>
                </div>
              </div>
              <pre>{JSON.stringify(exitResult.trade || exitResult, null, 2)}</pre>
            </div>
          )}

          <div className="webhookEvents">
            <div className="tradeReviewHeader">
              <div>
                <p className="eyebrow">Performance Analytics</p>
                <h4>가상 성과 분석</h4>
              </div>
              <div className="tradeReviewActions">
                <button className="secondaryButton" type="button" disabled={loading} onClick={onRefreshPerformance}>
                  <RefreshCw size={16} aria-hidden="true" />
                  성과 조회
                </button>
                <button className="secondaryButton" type="button" disabled={loading} onClick={onCreatePerformanceReport}>
                  <FileText size={16} aria-hidden="true" />
                  성과 리포트 생성
                </button>
              </div>
            </div>
            <p className="contextHint">
              실제 주문/체결 결과가 아닙니다. Paper Trading 기록에 대한 내부 가상 통계이며 simulation_only입니다.
            </p>
            {performance ? (
              <>
                <div className="webhookStatusGrid">
                  <div>
                    <span>총 가상 손익</span>
                    <strong>{Number(performance.total_pnl || 0).toFixed(2)}</strong>
                  </div>
                  <div>
                    <span>실현 손익</span>
                    <strong>{Number(performance.realized_pnl || 0).toFixed(2)}</strong>
                  </div>
                  <div>
                    <span>평가 손익</span>
                    <strong>{Number(performance.unrealized_pnl || 0).toFixed(2)}</strong>
                  </div>
                  <div>
                    <span>승률</span>
                    <strong>{Number(performance.win_rate || 0).toFixed(2)}%</strong>
                  </div>
                  <div>
                    <span>평균 수익</span>
                    <strong>{Number(performance.average_win || 0).toFixed(2)}</strong>
                  </div>
                  <div>
                    <span>평균 손실</span>
                    <strong>{Number(performance.average_loss || 0).toFixed(2)}</strong>
                  </div>
                  <div>
                    <span>Profit factor</span>
                    <strong>{performance.profit_factor ?? "N/A"}</strong>
                  </div>
                  <div>
                    <span>주문 실행 허용 여부</span>
                    <strong>{booleanKo(Boolean(performance.order_execution_allowed))}</strong>
                  </div>
                </div>
                <div className="autonomousGroups">
                  <PerformanceGroupList title="전략별 성과" groups={strategyGroups} />
                  <PerformanceGroupList title="판단별 성과" groups={decisionGroups} />
                  <PerformanceGroupList title="리스크 이벤트별 성과" groups={riskEventGroups} />
                  <PerformanceGroupList title="Watchlist별 성과" groups={watchlistGroups} />
                </div>
              </>
            ) : (
              <div className="emptyState">성과 분석을 조회하세요.</div>
            )}
            {performanceReport && (
              <div className="telegramResult">
                <strong>가상 성과 리포트 생성됨</strong>
                <p>{performanceReport.path}</p>
                <span>simulation_only: {String(Boolean(performanceReport.simulation_only))}</span>
              </div>
            )}
          </div>

          <div className="autonomousGroups">
            <div className="autonomousGroup">
              <h4>가상 포지션 평가</h4>
              {positions.length > 0 ? (
                positions.map((position) => (
                  <article key={position.id}>
                    <strong>{position.ticker}</strong>
                    <span>
                      수량 {Number(position.quantity || 0).toFixed(4)} · 평단{" "}
                      {Number(position.average_price || 0).toFixed(4)}
                    </span>
                    <span>
                      현재가 {Number(position.current_price || 0).toFixed(4)} · 평가 손익{" "}
                      {Number(position.unrealized_pnl || 0).toFixed(2)} (
                      {Number(position.unrealized_pnl_pct || 0).toFixed(2)}%)
                    </span>
                    <span>
                      가상 익절 {Number(position.take_profit_price || 0).toFixed(4)} · 가상 손절{" "}
                      {Number(position.stop_loss_price || 0).toFixed(4)}
                    </span>
                    <button
                      className="secondaryButton"
                      type="button"
                      disabled={loading || position.status !== "open"}
                      onClick={() => onSimulateExit(position.id)}
                    >
                      가상 청산
                    </button>
                  </article>
                ))
              ) : (
                <div className="emptyState">가상 포지션이 없습니다.</div>
              )}
            </div>
            <div className="autonomousGroup">
              <h4>가상 거래 기록</h4>
              {trades.length > 0 ? (
                trades.slice(0, 8).map((trade) => (
                  <article key={trade.id}>
                    <strong>
                      {trade.ticker} ·{" "}
                      {trade.action === "simulated_entry"
                        ? "가상 진입"
                        : trade.action === "simulated_exit"
                          ? "가상 청산"
                          : "가상 스킵"}
                    </strong>
                    <span>
                      {decisionLabel(trade.decision)} · {riskLevelLabel(trade.risk_level)} · {trade.simulation_status}
                    </span>
                    <span>
                      기준가 {Number(trade.base_price || 0).toFixed(4)} · 가상 가격{" "}
                      {Number(trade.simulated_price || trade.price || 0).toFixed(4)}
                    </span>
                    <span>
                      슬리피지 {Number(trade.slippage_bps || 0).toFixed(0)}bps · 스프레드{" "}
                      {Number(trade.spread_bps || 0).toFixed(0)}bps · 가상 금액{" "}
                      {Number(trade.notional || 0).toFixed(2)}
                    </span>
                    <span>실현 손익 {Number(trade.realized_pnl || 0).toFixed(2)}</span>
                  </article>
                ))
              ) : (
                <div className="emptyState">가상 거래 기록이 없습니다.</div>
              )}
            </div>
          </div>
        </>
      )}
      <SafetyBoundary />
    </section>
  );
}

function PerformanceGroupList({ title, groups }) {
  return (
    <div className="autonomousGroup">
      <h4>{title}</h4>
      {groups.length > 0 ? (
        groups.slice(0, 8).map((group) => (
          <article key={`${title}-${group.group_key || group.event_type || group.watchlist_id}`}>
            <strong>{group.group_key || group.event_type || group.watchlist_name || "unknown"}</strong>
            <span>
              거래 {group.trade_count || 0} · 진입 {group.entry_count || 0} · 청산 {group.exit_count || 0} · 스킵{" "}
              {group.skip_count || 0}
            </span>
            <span>
              총 가상 손익 {Number(group.total_pnl || 0).toFixed(2)} · 실현{" "}
              {Number(group.realized_pnl || 0).toFixed(2)} · 평가 {Number(group.unrealized_pnl || 0).toFixed(2)}
            </span>
            <span>승률 {Number(group.win_rate || 0).toFixed(2)}% · simulation_only</span>
          </article>
        ))
      ) : (
        <div className="emptyState">집계 가능한 가상 성과 기록이 없습니다.</div>
      )}
    </div>
  );
}

function WebhookPanel({
  status,
  events,
  tradeReviews,
  previewInput,
  setPreviewInput,
  previewProfile,
  setPreviewProfile,
  previewResult,
  previewLoading,
  onPreview,
  onRefresh,
  onOpenMeeting
}) {
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
      <div className="webhookPreview">
        <div className="tradeReviewHeader compact">
          <div>
            <p className="eyebrow">US Trader Oracle 호환성</p>
            <h4>Read-only Bridge 점검</h4>
          </div>
          <span className="statusPill">주문 실행 없음</span>
        </div>
        <p className="contextHint">
          Oracle live bot과 systemd service는 수정하지 않습니다. buy/sell 값은 주문이 아니라 검토용 context로만
          저장되고, quantity/order_type/stop_loss/take_profit 같은 주문 유사 필드는 adapter warning으로만 기록됩니다.
        </p>
        <div className="webhookStatusGrid">
          <div>
            <span>Mapping Profile</span>
            <strong>{previewProfile}</strong>
          </div>
          <div>
            <span>Review-only 처리</span>
            <strong>예</strong>
          </div>
          <div>
            <span>주문 유사 필드 감지</span>
            <strong>Adapter warnings</strong>
          </div>
          <div>
            <span>주문 실행 허용 여부</span>
            <strong>아니오</strong>
          </div>
        </div>
      </div>
      <div className="webhookPreview">
        <div className="tradeReviewHeader compact">
          <div>
            <p className="eyebrow">Oracle Sidecar 연동</p>
            <h4>Outbox 신호 파일 기반 계획</h4>
          </div>
          <span className="statusPill">Preview 우선</span>
        </div>
        <p className="contextHint">
          이 단계는 신호 export 구조 검증용입니다. Oracle 운영봇 직접 수정 없이 sample outbox 파일을
          normalize-preview로 검증하고, review-only 모드는 명시적으로 선택할 때만 사용합니다.
        </p>
        <div className="webhookStatusGrid">
          <div>
            <span>문서</span>
            <strong>docs/US_TRADER_ORACLE_SIDECAR_PLAN.md</strong>
          </div>
          <div>
            <span>샘플 Outbox</span>
            <strong>examples/oracle_sidecar/sample_outbox</strong>
          </div>
          <div>
            <span>Smoke test</span>
            <strong>scripts/run_oracle_sidecar_smoke.sh</strong>
          </div>
          <div>
            <span>주문 실행 허용 여부</span>
            <strong>아니오</strong>
          </div>
        </div>
        <pre className="commandSnippet">
{`python3 examples/oracle_sidecar/us_trader_signal_outbox_bridge.py \\
  --outbox examples/oracle_sidecar/sample_outbox \\
  --mode preview \\
  --dry-run \\
  --pretty`}
        </pre>
        <div className="webhookStatusGrid">
          <div>
            <span>Export Hook 패치 초안</span>
            <strong>examples/oracle_sidecar/patch_drafts</strong>
          </div>
          <div>
            <span>적용 전 사전점검</span>
            <strong>scripts/run_oracle_export_hook_preflight.sh</strong>
          </div>
          <div>
            <span>Outbox Export 방식</span>
            <strong>JSON atomic write</strong>
          </div>
          <div>
            <span>브로커 API 연결</span>
            <strong>없음</strong>
          </div>
        </div>
        <p className="contextHint">
          Export Hook 패치 초안은 Oracle 운영봇 직접 수정 전 반드시 검토해야 하는 문서와 helper 예시입니다.
          적용 전 preflight, sidecar dry-run, preview-only 검증을 먼저 통과해야 합니다.
        </p>
        <div className="webhookStatusGrid">
          <div>
            <span>Oracle 스테이징 리허설</span>
            <strong>scripts/run_oracle_staging_rehearsal.sh</strong>
          </div>
          <div>
            <span>Patch preview</span>
            <strong>로컬 복사본 전용</strong>
          </div>
          <div>
            <span>검증 순서</span>
            <strong>Patch preview / Preflight / Sidecar smoke</strong>
          </div>
          <div>
            <span>실제 Oracle 서버 수정</span>
            <strong>없음</strong>
          </div>
        </div>
        <p className="contextHint">
          운영봇 수정 전 로컬 staging copy에서 patch preview를 검증합니다. 이 단계는 실제 Oracle 서버를 수정하지
          않고 실제 주문을 실행하지 않습니다.
        </p>
      </div>
      <div className="webhookPreview">
        <div className="tradeReviewHeader compact">
          <div>
            <p className="eyebrow">Payload 호환성</p>
            <h4>Payload 정규화 미리보기</h4>
          </div>
          <button
            className="primaryButton"
            type="button"
            onClick={onPreview}
            disabled={previewLoading}
          >
            <RefreshCw size={16} aria-hidden="true" />
            {previewLoading ? "정규화 중..." : "정규화 미리보기"}
          </button>
        </div>
        <p className="contextHint">
          외부 봇 JSON을 붙여넣으면 trade review를 생성하지 않고 표준 payload와 adapter warning만 확인합니다.
          이 기능은 주문을 실행하지 않습니다.
        </p>
        <label className="fieldLabel">
          Mapping Profile
          <select value={previewProfile} onChange={(event) => setPreviewProfile(event.target.value)}>
            {WEBHOOK_PROFILE_OPTIONS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <textarea
          className="jsonTextarea"
          value={previewInput}
          onChange={(event) => setPreviewInput(event.target.value)}
          rows={12}
          spellCheck="false"
          aria-label="Webhook payload JSON"
        />
        {previewResult && (
          <div className="jsonResult">
            <div className="webhookStatusGrid">
              <div>
                <span>미리보기 상태</span>
                <strong>{previewResult.status}</strong>
              </div>
              <div>
                <span>거래 신호 검토 생성</span>
                <strong>{booleanKo(Boolean(previewResult.trade_review_created))}</strong>
              </div>
              <div>
                <span>주문 실행 허용 여부</span>
                <strong>{booleanKo(Boolean(previewResult.order_execution_allowed))}</strong>
              </div>
            </div>
            {previewResult.adapter_warnings?.length > 0 && (
              <div className="warningList">
                <strong>Adapter warnings</strong>
                <ul>
                  {previewResult.adapter_warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
            <pre>{JSON.stringify(previewResult.normalized_payload || previewResult, null, 2)}</pre>
          </div>
        )}
      </div>
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
                    {item.top_risk_event?.event_type && (
                      <span>
                        리스크 이벤트 {item.top_risk_event.event_type} · {riskLevelLabel(item.risk_event_severity)}
                      </span>
                    )}
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
  const riskEvents = result.risk_events || {};
  const topRiskEvent = riskEvents.top_event || {};
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
          <span>Top 리스크 이벤트</span>
          <strong>{topRiskEvent.event_type || "없음"}</strong>
        </div>
        <div>
          <span>리스크 이벤트 심각도</span>
          <strong>{topRiskEvent.severity ? riskLevelLabel(topRiskEvent.severity) : "없음"}</strong>
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
