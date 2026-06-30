const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: isFormData
      ? options.headers || {}
      : {
          "Content-Type": "application/json",
          ...(options.headers || {})
        },
    ...options
  });

  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      message = await response.text();
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

export const api = {
  baseUrl: API_BASE_URL,
  getHealth: () => request("/health"),
  getAgents: () => request("/api/agents"),
  getMarketDataStatus: () => request("/api/market-data/status"),
  getMarketDataQuote: (ticker) => request(`/api/market-data/quote/${encodeURIComponent(ticker)}`),
  getMarketDataSnapshot: (ticker) =>
    request(`/api/market-data/snapshot/${encodeURIComponent(ticker)}`),
  getMarketDataNews: (ticker) => request(`/api/market-data/news/${encodeURIComponent(ticker)}`),
  getMarketDataFilings: (ticker) =>
    request(`/api/market-data/filings/${encodeURIComponent(ticker)}`),
  getRiskEventStatus: () => request("/api/risk-events/status"),
  getRiskEventNews: (ticker) => request(`/api/risk-events/news/${encodeURIComponent(ticker)}`),
  getRiskEventFilings: (ticker) =>
    request(`/api/risk-events/filings/${encodeURIComponent(ticker)}`),
  getRiskEventDetection: (ticker) =>
    request(`/api/risk-events/detect/${encodeURIComponent(ticker)}`),
  getTelegramStatus: () => request("/api/telegram/status"),
  getWebhookStatus: () => request("/api/webhooks/status"),
  getWebhookEvents: () => request("/api/webhooks/events"),
  getWebhookEvent: (eventId) => request(`/api/webhooks/events/${eventId}`),
  normalizeWebhookPreview: (payload) =>
    request("/api/webhooks/normalize-preview", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getOperationsSummary: () => request("/api/operations/summary"),
  getOperationsRiskBrief: (limit = 20) => request(`/api/operations/risk-brief?limit=${limit}`),
  getOperationsScheduleHealth: () => request("/api/operations/schedule-health"),
  sendOperationsRiskBriefTelegram: (limit = 20) =>
    request(`/api/operations/risk-brief/telegram/send?limit=${limit}`, {
      method: "POST"
    }),
  getDiagnosticsSummary: () => request("/api/diagnostics/summary"),
  getDiagnosticsSecurity: () => request("/api/diagnostics/security"),
  getDiagnosticsProviders: () => request("/api/diagnostics/providers"),
  getDiagnosticsRuntime: () => request("/api/diagnostics/runtime"),
  getDiagnosticsE2EStatus: () => request("/api/diagnostics/e2e-status"),
  getMeetings: () => request("/api/meetings"),
  getTradeReviews: () => request("/api/trade-reviews"),
  getWatchlists: () => request("/api/watchlists"),
  getPaperPortfolios: () => request("/api/paper/portfolios"),
  getPaperPortfolio: (portfolioId) => request(`/api/paper/portfolios/${portfolioId}`),
  createPaperPortfolio: (payload) =>
    request("/api/paper/portfolios", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updatePaperPortfolio: (portfolioId, payload) =>
    request(`/api/paper/portfolios/${portfolioId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deletePaperPortfolio: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}`, {
      method: "DELETE"
    }),
  simulatePaperReview: (portfolioId, payload) =>
    request(`/api/paper/portfolios/${portfolioId}/simulate-review`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  simulatePaperExit: (portfolioId, positionId, payload) =>
    request(`/api/paper/portfolios/${portfolioId}/positions/${positionId}/simulate-exit`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  evaluatePaperExits: (portfolioId, payload) =>
    request(`/api/paper/portfolios/${portfolioId}/evaluate-exits`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getPaperPositions: (portfolioId) => request(`/api/paper/portfolios/${portfolioId}/positions`),
  getPaperTrades: (portfolioId) => request(`/api/paper/portfolios/${portfolioId}/trades`),
  getPaperSummary: (portfolioId) => request(`/api/paper/portfolios/${portfolioId}/summary`),
  getPaperPerformance: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}/performance`),
  getPaperPerformanceByStrategy: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}/performance/by-strategy`),
  getPaperPerformanceByDecision: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}/performance/by-decision`),
  getPaperPerformanceByRiskEvent: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}/performance/by-risk-event`),
  getPaperPerformanceByWatchlist: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}/performance/by-watchlist`),
  createPaperPerformanceReport: (portfolioId) =>
    request(`/api/paper/portfolios/${portfolioId}/performance/report`, {
      method: "POST"
    }),
  createWatchlist: (payload) =>
    request("/api/watchlists", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateWatchlist: (watchlistId, payload) =>
    request(`/api/watchlists/${watchlistId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteWatchlist: (watchlistId) =>
    request(`/api/watchlists/${watchlistId}`, {
      method: "DELETE"
    }),
  runWatchlistReview: (watchlistId) =>
    request(`/api/watchlists/${watchlistId}/run-review`, {
      method: "POST"
    }),
  getWatchlistReviews: () => request("/api/watchlist-reviews"),
  getWatchlistReview: (reviewId) => request(`/api/watchlist-reviews/${reviewId}`),
  sendWatchlistReviewTelegram: (reviewId) =>
    request(`/api/watchlist-reviews/${reviewId}/telegram/send`, {
      method: "POST"
    }),
  createWatchlistSchedule: (watchlistId, payload) =>
    request(`/api/watchlists/${watchlistId}/schedules`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getWatchlistSchedulesForWatchlist: (watchlistId) =>
    request(`/api/watchlists/${watchlistId}/schedules`),
  getWatchlistSchedules: () => request("/api/watchlist-schedules"),
  getWatchlistSchedule: (scheduleId) => request(`/api/watchlist-schedules/${scheduleId}`),
  updateWatchlistSchedule: (scheduleId, payload) =>
    request(`/api/watchlist-schedules/${scheduleId}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deleteWatchlistSchedule: (scheduleId) =>
    request(`/api/watchlist-schedules/${scheduleId}`, {
      method: "DELETE"
    }),
  runWatchlistScheduleNow: (scheduleId) =>
    request(`/api/watchlist-schedules/${scheduleId}/run-now`, {
      method: "POST"
    }),
  runDueWatchlistSchedules: () =>
    request("/api/watchlist-schedules/run-due", {
      method: "POST"
    }),
  getWatchlistScheduleRuns: (params = {}) => {
    const search = new URLSearchParams(
      Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== "")
    ).toString();
    return request(`/api/watchlist-schedule-runs${search ? `?${search}` : ""}`);
  },
  getWatchlistScheduleRun: (runId) => request(`/api/watchlist-schedule-runs/${runId}`),
  createTickerReview: (payload) =>
    request("/api/ticker-reviews", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createAutonomousReview: (payload) =>
    request("/api/autonomous-reviews", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  sendAutonomousReviewTelegram: (reviewId) =>
    request(`/api/autonomous-reviews/${reviewId}/telegram/send`, {
      method: "POST"
    }),
  createTradeReview: (payload) =>
    request("/api/trade-reviews", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getTradeReview: (tradeReviewId) => request(`/api/trade-reviews/${tradeReviewId}`),
  sendTradeReviewTelegram: (tradeReviewId) =>
    request(`/api/trade-reviews/${tradeReviewId}/telegram/send`, {
      method: "POST"
    }),
  createMeeting: (payload) =>
    request("/api/meetings", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getMeeting: (meetingId) => request(`/api/meetings/${meetingId}`),
  uploadMeetingFile: (meetingId, file) => {
    const formData = new FormData();
    formData.append("file", file);
    return request(`/api/meetings/${meetingId}/files`, {
      method: "POST",
      body: formData
    });
  },
  deleteFile: (fileId) =>
    request(`/api/files/${fileId}`, {
      method: "DELETE"
    }),
  runMeeting: (meetingId) =>
    request(`/api/meetings/${meetingId}/run`, {
      method: "POST"
    }),
  sendTelegram: (meetingId) =>
    request(`/api/meetings/${meetingId}/telegram/send`, {
      method: "POST"
    }),
  reportUrl: (meetingId) => `${API_BASE_URL}/api/meetings/${meetingId}/report`
};
