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
  getMeetings: () => request("/api/meetings"),
  getTradeReviews: () => request("/api/trade-reviews"),
  getWatchlists: () => request("/api/watchlists"),
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
