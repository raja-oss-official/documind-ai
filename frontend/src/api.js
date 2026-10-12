// ============================================================
// DOCUMIND AI API CLIENT
// ============================================================

// ============================================================
// CONFIGURATION
// ============================================================
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

const ACCESS_TOKEN_KEY = "documind_access_token";
const REFRESH_TOKEN_KEY = "documind_refresh_token";

export const MAX_UPLOAD_SIZE = 10 * 1024 * 1024;

export const SUPPORTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".txt",
  ".csv",
  ".xlsx",
  ".pptx",
  ".png",
  ".jpg",
  ".jpeg",
];

// ============================================================
// TOKEN STORAGE
// ============================================================

function readStorage(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    if (value) {
      window.localStorage.setItem(key, value);
    } else {
      window.localStorage.removeItem(key);
    }
  } catch {
    // Storage can be unavailable (private mode); tokens stay in memory.
  }
}

// ============================================================
// SESSION STATE
// ============================================================
let accessToken = readStorage(ACCESS_TOKEN_KEY);
let refreshToken = readStorage(REFRESH_TOKEN_KEY);
let refreshPromise = null;
let sessionExpiredHandler = null;

export function hasSession() {
  return Boolean(accessToken || refreshToken);
}

export function setTokens(nextAccessToken, nextRefreshToken) {
  accessToken = nextAccessToken || null;
  refreshToken = nextRefreshToken || null;
  writeStorage(ACCESS_TOKEN_KEY, accessToken);
  writeStorage(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens() {
  setTokens(null, null);
}

export function onSessionExpired(handler) {
  sessionExpiredHandler = handler;
}

// ============================================================
// ERRORS
// ============================================================

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function extractErrorMessage(data, status) {
  const detail = data?.detail;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item.msg || "").replace(/^Value error, /, ""))
      .filter(Boolean)
      .join(", ");
  }

  if (typeof detail === "string") {
    return detail;
  }

  // slowapi rate-limit responses use the "error" key.
  if (typeof data?.error === "string") {
    return status === 429
      ? `Too many requests. ${data.error}. Please wait and try again.`
      : data.error;
  }

  return "The request failed. Please try again.";
}

// ============================================================
// CORE REQUEST
// ============================================================

async function rawRequest(path, { method = "GET", body, query, auth = true } = {}) {
  const url = new URL(`${API_BASE_URL}${path}`);

  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    });
  }

  const headers = {};
  let requestBody;

  if (body instanceof FormData) {
    requestBody = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  if (auth && accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  let response;

  try {
    response = await fetch(url, { method, headers, body: requestBody });
  } catch {
    throw new ApiError(
      `Cannot reach the backend. Make sure FastAPI is running at ${
        new URL(API_BASE_URL).origin
      }.`,
      0
    );
  }

  const data = await response.json().catch(() => ({}));

  return { response, data };
}

async function refreshAccessToken() {
  if (!refreshToken) {
    return false;
  }

  if (!refreshPromise) {
    refreshPromise = rawRequest("/auth/refresh", {
      method: "POST",
      query: { refresh_token: refreshToken },
      auth: false,
    })
      .then(({ response, data }) => {
        if (!response.ok || !data.access_token) {
          return false;
        }

        setTokens(data.access_token, data.refresh_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null;
      });
  }

  return refreshPromise;
}

export async function request(path, options = {}) {
  const auth = options.auth !== false;

  let { response, data } = await rawRequest(path, options);

  // Access tokens expire after 30 minutes; rotate once and retry.
  if (response.status === 401 && auth) {
    const refreshed = await refreshAccessToken();

    if (refreshed) {
      ({ response, data } = await rawRequest(path, options));
    }

    if (response.status === 401) {
      clearTokens();
      sessionExpiredHandler?.();
      throw new ApiError("Your session has expired. Please sign in again.", 401);
    }
  }

  if (!response.ok) {
    throw new ApiError(extractErrorMessage(data, response.status), response.status);
  }

  return data;
}

// ============================================================
// HEALTH
// ============================================================

export const checkHealth = () => request("/health", { auth: false });

// ============================================================
// AUTHENTICATION
// ============================================================

export const registerUser = ({ name, email, password }) =>
  request("/auth/register", {
    method: "POST",
    body: { name, email, password },
    auth: false,
  });

export async function loginUser({ email, password }) {
  const data = await request("/auth/login", {
    method: "POST",
    body: { email, password },
    auth: false,
  });

  if (!data.access_token) {
    throw new ApiError("The login response did not contain an access token.", 0);
  }

  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function logoutUser() {
  const token = refreshToken;
  clearTokens();

  if (!token) {
    return;
  }

  // Revoke the refresh token server-side; local sign-out happens regardless.
  await rawRequest("/auth/logout", {
    method: "POST",
    query: { refresh_token: token },
    auth: false,
  }).catch(() => {});
}

export const getCurrentUser = () => request("/auth/me");

export const changePassword = ({ currentPassword, newPassword }) =>
  request("/auth/change-password", {
    method: "POST",
    body: {
      current_password: currentPassword,
      new_password: newPassword,
    },
  });

// ============================================================
// DOCUMENTS
// ============================================================

export const listDocuments = () => request("/documents");

export const getDocument = (documentId) => request(`/documents/${documentId}`);

export function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  return request("/documents/upload", { method: "POST", body: formData });
}

export const deleteDocument = (documentId) =>
  request(`/documents/${documentId}`, { method: "DELETE" });

export const renameDocument = (documentId, filename) =>
  request(`/documents/${documentId}/rename`, {
    method: "PATCH",
    body: { filename },
  });

export const generateSummary = (documentId) =>
  request(`/documents/${documentId}/summary`, { method: "POST" });

export const searchDocuments = ({ query, documentId, limit = 5 }) =>
  request("/documents/search", {
    query: { q: query, document_id: documentId, limit },
  });

export const askDocuments = (question) =>
  request("/documents/ask", { method: "POST", body: { question } });

// ============================================================
// CHATS
// ============================================================

export const listChats = () => request("/chats");

export const createChat = ({ title, documentId }) =>
  request("/chats", {
    method: "POST",
    body: {
      title: title || "New Chat",
      document_id: documentId || null,
    },
  });

export const updateChat = (sessionId, { title, documentId }) =>
  request(`/chats/${sessionId}`, {
    method: "PATCH",
    body: {
      ...(title !== undefined && { title }),
      ...(documentId !== undefined && { document_id: documentId }),
    },
  });

export const deleteChat = (sessionId) =>
  request(`/chats/${sessionId}`, { method: "DELETE" });

export const getChatMessages = (sessionId) =>
  request(`/chats/${sessionId}/messages`);

// Saves a user message without asking the AI (a note in the conversation).
export const addChatNote = (sessionId, content) =>
  request(`/chats/${sessionId}/messages`, {
    method: "POST",
    body: { content },
  });

export const askInChat = (sessionId, question) =>
  request(`/chats/${sessionId}/ask`, {
    method: "POST",
    body: { question },
  });

// ============================================================
// FORMATTING HELPERS
// ============================================================

export function formatFileSize(bytes = 0) {
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function formatDate(value) {
  if (!value) {
    return "";
  }

  // Backend datetimes are UTC; naive ISO strings need a "Z".
  const text = String(value);
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`);

  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

export function formatMessageTime(value) {
  if (!value) {
    return "";
  }

  const text = String(value);
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  const time = date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  return date.toDateString() === new Date().toDateString()
    ? time
    : `${date.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`;
}

export function formatRelativeTime(value) {
  if (!value) {
    return "";
  }

  const text = String(value);
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`);
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);

  if (Number.isNaN(seconds)) {
    return "";
  }

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  if (seconds < 7 * 86400) return `${Math.floor(seconds / 86400)} d ago`;

  return date.toLocaleDateString();
}

export function fileExtension(filename = "") {
  const index = filename.lastIndexOf(".");
  return index >= 0 ? filename.slice(index).toLowerCase() : "";
}
