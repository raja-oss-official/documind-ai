// ============================================================
// DOCUMIND AI LOCAL STORAGE
// ============================================================
// Browser-only conveniences: theme, saved answer sources, search
// history. Nothing here is required for the app to work; every read
// and write tolerates storage being unavailable (private mode).

// ============================================================
// KEYS
// ============================================================
const PREFIX = "documind_";

// Per-user data (sources, searches) is cleared on sign out.
const USER_PREFIX = `${PREFIX}user_`;

export const THEME_KEY = `${PREFIX}theme`;

export const userKey = (userId, name) => `${USER_PREFIX}${userId || "anonymous"}_${name}`;

// ============================================================
// READ AND WRITE
// ============================================================

export function readJSON(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function writeJSON(key, value) {
  try {
    if (value === undefined || value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {
    // Storage full or unavailable; the feature simply isn't remembered.
  }
}

// ============================================================
// CLEAR PER-USER DATA (SIGN OUT)
// ============================================================

export function clearUserData() {
  try {
    Object.keys(window.localStorage)
      .filter((key) => key.startsWith(USER_PREFIX))
      .forEach((key) => window.localStorage.removeItem(key));
  } catch {
    // Storage unavailable; nothing to clear.
  }
}
