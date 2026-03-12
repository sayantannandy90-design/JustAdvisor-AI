const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const headers = { "Content-Type": "application/json" };

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, { headers, ...options });
  if (!res.ok) {
    let detail;
    try {
      const err = await res.json();
      detail = err.detail || err.error || res.statusText;
    } catch { detail = res.statusText; }
    throw new Error(typeof detail === "object" ? JSON.stringify(detail) : detail);
  }
  return res.json();
}

export const api = {
  saveMessage: (caseId, lawyer, role, content) =>
    request(`/debate/${caseId}/message`, {
      method: "POST",
      body: JSON.stringify({ lawyer, role, content }),
    }),

  getMessages: (caseId) => request(`/debate/${caseId}/messages`),

  listDebates: () => request("/debates"),

  generateJudgment: (caseId, caseTitle, lawyerAMessages, lawyerBMessages) =>
    request(`/judgment/${caseId}`, {
      method: "POST",
      body: JSON.stringify({ caseTitle, lawyerAMessages, lawyerBMessages }),
    }),

  getJudgment: (caseId) => request(`/judgment/${caseId}`),

  getAdvisorHint: (caseId, side, argument, case_context = "") =>
    request(`/advisor/${caseId}/${side}`, {
      method: "POST",
      body: JSON.stringify({ argument, case_context }),
    }),

  health: () => request("/health"),
};

export default api;