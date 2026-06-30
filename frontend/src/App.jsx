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

function statusLabel(status) {
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  if (status === "running") return "Running";
  return "Draft";
}

function stageIcon(stage) {
  if (stage === "summary") return <Scale size={18} aria-hidden="true" />;
  if (stage === "rebuttal") return <AlertTriangle size={18} aria-hidden="true" />;
  return <Brain size={18} aria-hidden="true" />;
}

function modeLabel(mode) {
  return (mode || "quick_review").replaceAll("_", " ");
}

export default function App() {
  const [agents, setAgents] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [tradeReviews, setTradeReviews] = useState([]);
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
  const [tradeReviewResult, setTradeReviewResult] = useState(null);
  const [tradeReviewTelegramResult, setTradeReviewTelegramResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tradeReviewLoading, setTradeReviewLoading] = useState(false);
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
      const [agentList, telegram, reviewList, hooks, events] = await Promise.all([
        api.getAgents(),
        api.getTelegramStatus(),
        api.getTradeReviews(),
        api.getWebhookStatus(),
        api.getWebhookEvents()
      ]);
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
            <p>Mock agent review room</p>
          </div>
        </div>

        <form className="createForm" onSubmit={handleCreate}>
          <label>
            <span>Topic</span>
            <textarea
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              placeholder="Analyze TEST breakout risk"
              rows={4}
            />
          </label>
          <label>
            <span>Ticker</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value)}
              placeholder="Optional"
              maxLength={16}
            />
          </label>
          <label>
            <span>Mode</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="quick_review">Quick review</option>
              <option value="deep_debate">Deep debate</option>
              <option value="skeptic_review">Skeptic review</option>
              <option value="risk_gate_review">Risk gate review</option>
              <option value="action_plan">Action plan</option>
            </select>
          </label>
          <button className="primaryButton" type="submit" disabled={loading || !topic.trim()}>
            <Plus size={18} aria-hidden="true" />
            Create meeting
          </button>
        </form>

        <div className="sidebarHeader">
          <span>Meetings</span>
          <button
            className="iconButton"
            type="button"
            title="Refresh meetings"
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
                {meeting.ticker || "No ticker"} · {statusLabel(meeting.status)}
              </span>
            </button>
          ))}
          {meetings.length === 0 && <div className="emptyState">No meetings yet</div>}
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">AI Council Workspace</p>
            <h2>{selectedMeeting?.topic || "Create a council meeting"}</h2>
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
              Run council
            </button>
            <a
              className={`secondaryButton ${detail?.report?.available ? "" : "disabled"}`}
              href={selectedId && detail?.report?.available ? api.reportUrl(selectedId) : undefined}
              target="_blank"
              rel="noreferrer"
            >
              <FileText size={18} aria-hidden="true" />
              Report
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
            <span>{agents.length} seeded agents</span>
          </div>
          <div>
            <Shield size={18} aria-hidden="true" />
            <span>No broker execution</span>
          </div>
          <div>
            <CheckCircle2 size={18} aria-hidden="true" />
            <span>
              {selectedMeeting
                ? `${statusLabel(selectedMeeting.status)} · ${modeLabel(selectedMeeting.mode)}`
                : "Ready"}
            </span>
          </div>
        </section>

        <WebhookPanel
          status={webhookStatus}
          events={webhookEvents}
          tradeReviews={tradeReviews}
          onRefresh={refreshWebhookData}
          onOpenMeeting={handleSelect}
        />

        <section className="tradeReviewSection">
          <div className="tradeReviewHeader">
            <div>
              <p className="eyebrow">Phase 7 Read-only Review</p>
              <h3>Trade Signal Review</h3>
            </div>
            <span>order_execution_allowed=false</span>
          </div>
          <form className="tradeReviewForm" onSubmit={handleTradeReviewSubmit}>
            <label>
              <span>Ticker</span>
              <input
                value={tradeReviewForm.ticker}
                onChange={(event) => updateTradeReviewField("ticker", event.target.value)}
                placeholder="ABCD"
                maxLength={16}
              />
            </label>
            <label>
              <span>Signal</span>
              <input
                value={tradeReviewForm.strategy_signal}
                onChange={(event) =>
                  updateTradeReviewField("strategy_signal", event.target.value)
                }
                placeholder="breakout"
              />
            </label>
            <label>
              <span>Side context</span>
              <select
                value={tradeReviewForm.side}
                onChange={(event) => updateTradeReviewField("side", event.target.value)}
              >
                <option value="watch_only">watch_only</option>
                <option value="review_only">review_only</option>
                <option value="buy">buy as context</option>
                <option value="sell">sell as context</option>
              </select>
            </label>
            <label>
              <span>Price</span>
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
              <span>Volume</span>
              <input
                type="number"
                min="0"
                value={tradeReviewForm.volume}
                onChange={(event) => updateTradeReviewField("volume", event.target.value)}
                placeholder="12500000"
              />
            </label>
            <label>
              <span>Timeframe</span>
              <input
                value={tradeReviewForm.timeframe}
                onChange={(event) => updateTradeReviewField("timeframe", event.target.value)}
                placeholder="1m"
              />
            </label>
            <label>
              <span>Spread %</span>
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
              <span>Premarket</span>
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
              <span>VWAP distance</span>
              <input
                type="number"
                step="0.001"
                value={tradeReviewForm.vwap_distance}
                onChange={(event) => updateTradeReviewField("vwap_distance", event.target.value)}
                placeholder="0.04"
              />
            </label>
            <label className="wideField">
              <span>News headlines</span>
              <textarea
                value={tradeReviewForm.news_headlines}
                onChange={(event) =>
                  updateTradeReviewField("news_headlines", event.target.value)
                }
                rows={3}
                placeholder="One headline per line"
              />
            </label>
            <label className="wideField">
              <span>Notes</span>
              <textarea
                value={tradeReviewForm.notes}
                onChange={(event) => updateTradeReviewField("notes", event.target.value)}
                rows={3}
                placeholder="candidate signal generated by existing bot"
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
              Submit for review
            </button>
          </form>
          <p className="contextHint">
            Trade Review accepts external bot candidates as read-only context and never creates,
            sends, or routes orders.
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
              <h4>Recent trade reviews</h4>
              <div>
                {tradeReviews.slice(0, 4).map((review) => (
                  <button
                    type="button"
                    key={review.id}
                    onClick={() => handleSelect(review.linked_meeting_id)}
                  >
                    <strong>{review.ticker}</strong>
                    <span>
                      {review.decision} · {review.risk_level} ·{" "}
                      {String(review.order_execution_allowed)}
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
              <OutputGroup title="Agent Analysis" outputs={groupedOutputs.analysis} />
              <OutputGroup title="Skeptic Rebuttal" outputs={groupedOutputs.rebuttal} />
              <OutputGroup title="Chairman Summary" outputs={groupedOutputs.summary} />
            </div>

            <aside className="reviewPanel">
              <h3>Trade Review Scaffold</h3>
              <dl>
                <div>
                  <dt>Mode</dt>
                  <dd>{modeLabel(selectedMeeting.mode)}</dd>
                </div>
                <div>
                  <dt>Mock only</dt>
                  <dd>{String(selectedMeeting.trade_review?.mock_only)}</dd>
                </div>
                <div>
                  <dt>Orders allowed</dt>
                  <dd>{String(selectedMeeting.trade_review?.order_execution_allowed)}</dd>
                </div>
                <div>
                  <dt>Risk gate</dt>
                  <dd>{selectedMeeting.trade_review?.risk_gate_status || "future_required"}</dd>
                </div>
                <div>
                  <dt>Broker</dt>
                  <dd>{selectedMeeting.trade_review?.broker_integration_status || "not_connected"}</dd>
                </div>
              </dl>

              <div className="telegramPanel">
                <div className="panelHeading">
                  <h3>Telegram</h3>
                  <span>{telegramStatus?.configured ? "ON" : "OFF"}</span>
                </div>
                <p className="contextHint">
                  {telegramStatus?.configured
                    ? "Report delivery is configured for this backend."
                    : "Telegram is disabled or missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID."}
                </p>
                <button
                  className="secondaryButton"
                  type="button"
                  disabled={!selectedId || telegramLoading}
                  onClick={handleSendTelegram}
                >
                  <Send size={17} aria-hidden="true" />
                  Send to Telegram
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
                  <h3>Context Files</h3>
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
                    Upload
                  </button>
                </form>
                <p className="contextHint">
                  Uploaded text summaries are included in the next council run as meeting context.
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
                        title="Delete file"
                        disabled={fileLoading}
                        onClick={() => handleDeleteFile(file.id)}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    </div>
                  ))}
                  {contextFiles.length === 0 && (
                    <div className="emptyState">No context files attached</div>
                  )}
                </div>
              </div>
            </aside>
          </section>
        ) : (
          <section className="blankSlate">
            <Brain size={44} aria-hidden="true" />
            <h3>No meeting selected</h3>
            <p>Create a topic to start the mock council workflow.</p>
          </section>
        )}
      </main>
    </div>
  );
}

function DecisionCard({ decision }) {
  const hasDecision = Boolean(decision?.decision);
  return (
    <section className="decisionCard">
      <div className="decisionHeader">
        <div>
          <p className="eyebrow">Structured Decision</p>
          <h3>{hasDecision ? decision.decision : "Pending"}</h3>
        </div>
        <div className="badgeGroup">
          <span className={`decisionBadge ${hasDecision ? decision.decision?.toLowerCase() : ""}`}>
            {hasDecision ? decision.decision : "DRAFT"}
          </span>
          <span className={`riskBadge ${hasDecision ? decision.risk_level : ""}`}>
            {hasDecision ? decision.risk_level : "unrated"}
          </span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>Confidence</span>
          <strong>{hasDecision ? Math.round(decision.confidence * 100) : 0}%</strong>
        </div>
        <div>
          <span>Trade allowed</span>
          <strong>{String(Boolean(decision.trade_allowed))}</strong>
        </div>
        <div>
          <span>Orders allowed</span>
          <strong>{String(Boolean(decision.order_execution_allowed))}</strong>
        </div>
        <div>
          <span>Size multiplier</span>
          <strong>{hasDecision ? decision.position_size_multiplier : 0}</strong>
        </div>
      </div>
      {hasDecision && (
        <div className="decisionLists">
          <div>
            <h4>Risk Flags</h4>
            {(decision.risk_flags || []).slice(0, 6).map((flag) => (
              <span key={flag}>{flag}</span>
            ))}
          </div>
          <div>
            <h4>Required Follow-up</h4>
            {(decision.required_follow_up || []).slice(0, 4).map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function WebhookPanel({ status, events, tradeReviews, onRefresh, onOpenMeeting }) {
  const endpoint = `${api.baseUrl}${status?.endpoint || "/api/webhooks/trade-signal"}`;
  const reviewById = new Map(tradeReviews.map((review) => [review.id, review]));
  return (
    <section className="webhookPanel">
      <div className="tradeReviewHeader">
        <div>
          <p className="eyebrow">External Bot Webhook</p>
          <h3>Webhook Receiver</h3>
        </div>
        <button className="iconButton" type="button" title="Refresh webhooks" onClick={onRefresh}>
          <RefreshCw size={17} aria-hidden="true" />
        </button>
      </div>
      <div className="webhookStatusGrid">
        <div>
          <span>Enabled</span>
          <strong>{String(Boolean(status?.enabled))}</strong>
        </div>
        <div>
          <span>Configured</span>
          <strong>{String(Boolean(status?.configured))}</strong>
        </div>
        <div>
          <span>Secret required</span>
          <strong>{String(Boolean(status?.require_secret))}</strong>
        </div>
        <div>
          <span>Orders allowed</span>
          <strong>{String(Boolean(status?.order_execution_allowed))}</strong>
        </div>
      </div>
      <div className="endpointRow">
        <span>Endpoint</span>
        <code>{endpoint}</code>
      </div>
      <p className="contextHint">
        Header: {status?.secret_header || "X-AI-Council-Webhook-Secret"}. Secret value is never
        exposed in the UI.
      </p>
      {status?.disabled_reason && <p className="contextHint">{status.disabled_reason}</p>}
      <div className="webhookEvents">
        <h4>Recent webhook events</h4>
        {events.length > 0 ? (
          events.slice(0, 5).map((event) => {
            const review = reviewById.get(event.trade_review_id);
            return (
              <article key={event.id}>
                <div>
                  <strong>{event.source}</strong>
                  <span>
                    {event.signal_id} · {event.status} · duplicated false
                  </span>
                </div>
                <div>
                  <span>Trade review</span>
                  <strong>{event.trade_review_id ? event.trade_review_id.slice(0, 8) : "none"}</strong>
                </div>
                <button
                  className="secondaryButton"
                  type="button"
                  disabled={!review?.linked_meeting_id}
                  onClick={() => review?.linked_meeting_id && onOpenMeeting(review.linked_meeting_id)}
                >
                  <FileText size={16} aria-hidden="true" />
                  Open
                </button>
              </article>
            );
          })
        ) : (
          <div className="emptyState">No webhook events yet</div>
        )}
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
          <p className="eyebrow">Review Result</p>
          <h3>
            {review.ticker} · {decision.decision || review.decision}
          </h3>
        </div>
        <div className="badgeGroup">
          <span className={`decisionBadge ${(decision.decision || review.decision || "").toLowerCase()}`}>
            {decision.decision || review.decision}
          </span>
          <span className={`riskBadge ${decision.risk_level || review.risk_level}`}>
            {decision.risk_level || review.risk_level}
          </span>
        </div>
      </div>
      <div className="decisionMetrics">
        <div>
          <span>Confidence</span>
          <strong>{decision.confidence ? Math.round(decision.confidence * 100) : 0}%</strong>
        </div>
        <div>
          <span>Trade allowed</span>
          <strong>{String(Boolean(decision.trade_allowed))}</strong>
        </div>
        <div>
          <span>Orders allowed</span>
          <strong>{String(Boolean(decision.order_execution_allowed))}</strong>
        </div>
        <div>
          <span>Linked meeting</span>
          <strong>{linkedMeetingId ? linkedMeetingId.slice(0, 8) : "none"}</strong>
        </div>
      </div>
      <div className="decisionLists">
        <div>
          <h4>Risk Flags</h4>
          {(decision.risk_flags || []).slice(0, 6).map((flag) => (
            <span key={flag}>{flag}</span>
          ))}
        </div>
        <div>
          <h4>Follow-up</h4>
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
          Open linked meeting
        </button>
        <a
          className={`secondaryButton ${result.report?.available ? "" : "disabled"}`}
          href={linkedMeetingId && result.report?.available ? api.reportUrl(linkedMeetingId) : undefined}
          target="_blank"
          rel="noreferrer"
        >
          <FileText size={17} aria-hidden="true" />
          Report
        </a>
        <button
          className="secondaryButton"
          type="button"
          disabled={!review.id || loading}
          onClick={onSendTelegram}
        >
          <Send size={17} aria-hidden="true" />
          Send review
        </button>
      </div>
      <p className="contextHint">
        Telegram status: {telegramConfigured ? "configured" : "disabled or missing settings"}
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
      <p>{SAFETY_BOUNDARY}</p>
    </section>
  );
}

function RoundList({ messages }) {
  const rounds = [
    ["initial_opinion", "Agent Initial Opinions"],
    ["rebuttal", "Rebuttals"],
    ["revision", "Revised Notes"],
    ["chairman_summary", "Chairman Summary"],
    ["structured_decision", "Structured Decision"]
  ];
  return (
    <section className="roundPanel">
      <h3>Debate Rounds</h3>
      {rounds.map(([round, title]) => {
        const roundMessages = messages.filter((message) => message.round === round);
        return (
          <div className="roundGroup" key={round}>
            <h4>{title}</h4>
            {roundMessages.length > 0 ? (
              roundMessages.map((message) => (
                <article className="roundMessage" key={message.id || `${round}-${message.agent_key}`}>
                  <div>
                    <strong>{message.agent_name}</strong>
                    <span>
                      {message.message_type} · {message.risk_level} ·{" "}
                      {Math.round(message.confidence * 100)}%
                    </span>
                  </div>
                  <p>{message.content}</p>
                </article>
              ))
            ) : (
              <div className="emptyState">Run the council to generate this round</div>
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
                  <h4>{output.agent_name}</h4>
                  <p>{output.stance} · confidence {Math.round(output.confidence * 100)}%</p>
                </div>
              </div>
              <p className="outputContent">{output.content}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="emptyState">Run the council to generate this section</div>
      )}
    </section>
  );
}
