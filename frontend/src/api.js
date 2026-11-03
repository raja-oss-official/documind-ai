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

  // FastAPI's own "Not Found" means the route does not exist: the
  // server is running an older version than this app.
  if (detail === "Not Found" && status === 404) {
    return "This feature isn't available on the server yet. The backend needs to be redeployed with the latest version.";
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

// Local development points at FastAPI on this machine; the deployed
// app talks to a server that sleeps when idle on the free plan.
function unreachableMessage() {
  const origin = new URL(API_BASE_URL).origin;

  return /localhost|127\.0\.0\.1/.test(origin)
    ? `Cannot reach the backend. Make sure FastAPI is running at ${origin}.`
    : "Can't reach the DocuMind AI server right now. It may be waking up or restarting, which can take up to a minute. Please try again shortly.";
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
    throw new ApiError(unreachableMessage(), 0);
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

// Polls a document until background processing finishes.
export async function waitForDocument(documentId, { interval = 2000, timeout = 15 * 60 * 1000 } = {}) {
  const started = Date.now();

  for (;;) {
    const document = await getDocument(documentId);

    if (document.status !== "processing" || Date.now() - started > timeout) {
      return document;
    }

    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}

// ============================================================
// YOUTUBE VIDEOS
// ============================================================

// Adds a public video by link; Gemini transcribes it in the background.
export const addYouTubeVideo = (url) =>
  request("/youtube", { method: "POST", body: { url } });

export const isVideo = (document) => document?.processing_type === "youtube";

// "[03:12]" / "[1:02:03]" → seconds; null when the text has no timestamp.
export function parseTimestamp(text = "") {
  const match = String(text).match(/\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]/);
  return match ? Number(match[1] || 0) * 3600 + Number(match[2]) * 60 + Number(match[3]) : null;
}

export function formatTimestamp(seconds = 0) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = String(Math.floor(seconds % 60)).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${String(m).padStart(2, "0")}:${s}`;
}

// ============================================================
// DOCUMENT TOOLS
// ============================================================

export const compareDocuments = (documentIds, focus) =>
  request("/documents/compare", {
    method: "POST",
    body: { document_ids: documentIds, focus: focus || null },
  });

export const generateStudySet = (documentId, type, count = 8) =>
  request(`/documents/${documentId}/study`, {
    method: "POST",
    body: { type, count },
  });

export const extractFacts = (documentId) =>
  request(`/documents/${documentId}/facts`, { method: "POST" });

// The original file as a Blob (fetched with the access token).
export async function getDocumentFile(documentId) {
  const fetchFile = () =>
    fetch(`${API_BASE_URL}/documents/${documentId}/file`, {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    });

  let response;

  try {
    response = await fetchFile();

    if (response.status === 401 && (await refreshAccessToken())) {
      response = await fetchFile();
    }
  } catch {
    throw new ApiError(unreachableMessage(), 0);
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(extractErrorMessage(data, response.status), response.status);
  }

  return response.blob();
}

// ============================================================
// SHARING
// ============================================================

export const listDocumentShares = (documentId) => request(`/documents/${documentId}/shares`);

export const shareDocument = (documentId, { email, role }) =>
  request(`/documents/${documentId}/shares`, {
    method: "POST",
    body: { email, role },
  });

export const removeDocumentShare = (documentId, userId) =>
  request(`/documents/${documentId}/shares/${userId}`, { method: "DELETE" });

export const listChatShares = (sessionId) => request(`/chats/${sessionId}/shares`);

export const shareChat = (sessionId, { email }) =>
  request(`/chats/${sessionId}/shares`, {
    method: "POST",
    body: { email },
  });

export const removeChatShare = (sessionId, userId) =>
  request(`/chats/${sessionId}/shares/${userId}`, { method: "DELETE" });

export const listSharedChats = () => request("/chats/shared");

export const getSharedChatMessages = (sessionId) => request(`/chats/shared/${sessionId}/messages`);

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
// STREAMING CHAT ANSWERS (SERVER-SENT EVENTS)
// ============================================================
// Calls onEvent(name, data) for "start", "token" (many), "done"
// and "error". Retries once after refreshing an expired token.
export async function askInChatStream(sessionId, question, onEvent) {
  const send = () =>
    fetch(`${API_BASE_URL}/chats/${sessionId}/ask/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken && { Authorization: `Bearer ${accessToken}` }),
      },
      body: JSON.stringify({ question }),
    });

  let response;

  try {
    response = await send();

    if (response.status === 401 && (await refreshAccessToken())) {
      response = await send();
    }
  } catch {
    throw new ApiError(unreachableMessage(), 0);
  }

  if (response.status === 401) {
    clearTokens();
    sessionExpiredHandler?.();
    throw new ApiError("Your session has expired. Please sign in again.", 401);
  }

  if (!response.ok || !response.body) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(extractErrorMessage(data, response.status), response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();

    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });

    // Events are separated by a blank line: "event: x\ndata: {...}\n\n".
    let end = buffer.indexOf("\n\n");

    while (end >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      end = buffer.indexOf("\n\n");

      const name = block.match(/^event: (.*)$/m)?.[1];
      const data = block.match(/^data: (.*)$/m)?.[1];

      if (name && data) {
        onEvent(name, JSON.parse(data));
      }
    }
  }
}

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
