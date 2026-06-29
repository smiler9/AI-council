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
  getAgents: () => request("/api/agents"),
  getTelegramStatus: () => request("/api/telegram/status"),
  getMeetings: () => request("/api/meetings"),
  getTradeReviews: () => request("/api/trade-reviews"),
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
