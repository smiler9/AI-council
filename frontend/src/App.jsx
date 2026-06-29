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
  Shield
} from "lucide-react";
import { api } from "./api";

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

export default function App() {
  const [agents, setAgents] = useState([]);
  const [meetings, setMeetings] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [topic, setTopic] = useState("");
  const [ticker, setTicker] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const selectedMeeting = detail?.meeting;

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
      const [agentList] = await Promise.all([api.getAgents()]);
      setAgents(agentList);
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
        ticker: ticker.trim() || null
      });
      setTopic("");
      setTicker("");
      await loadMeetings(meeting.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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
        report: payload.report
      });
      await loadMeetings(selectedId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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
            <p className="eyebrow">Phase 1 MVP</p>
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
            <span>{selectedMeeting ? statusLabel(selectedMeeting.status) : "Ready"}</span>
          </div>
        </section>

        {selectedMeeting ? (
          <section className="detailGrid">
            <div className="outputColumn">
              <OutputGroup title="Agent Analysis" outputs={groupedOutputs.analysis} />
              <OutputGroup title="Skeptic Rebuttal" outputs={groupedOutputs.rebuttal} />
              <OutputGroup title="Chairman Summary" outputs={groupedOutputs.summary} />
            </div>

            <aside className="reviewPanel">
              <h3>Trade Review Scaffold</h3>
              <dl>
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
