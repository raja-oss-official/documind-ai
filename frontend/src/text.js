// ============================================================
// TEXT HELPERS (HIGHLIGHTING AND PLAIN TEXT)
// ============================================================

// ============================================================
// QUERY TERMS
// ============================================================
// Words worth highlighting in a passage. Mirrors the backend's keyword
// scoring: lower-case, letters and digits, common words removed.
const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does",
  "for", "from", "how", "in", "is", "it", "its", "me", "my", "of", "on",
  "or", "please", "tell", "that", "the", "this", "to", "was", "what",
  "when", "where", "which", "who", "why", "with", "you", "your",
]);

export function queryTerms(query = "") {
  const words = query.toLowerCase().match(/[a-z0-9]+/g) || [];
  return [...new Set(words.filter((word) => word.length > 1 && !STOP_WORDS.has(word)))];
}

// Splits text into [{ text, match }] parts so matches can be wrapped in <mark>.
export function splitByTerms(text = "", terms = []) {
  if (terms.length === 0) {
    return [{ text, match: false }];
  }

  const escaped = terms.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`\\b(${escaped.join("|")})\\w*`, "gi");
  const parts = [];
  let last = 0;

  for (const found of text.matchAll(pattern)) {
    if (found.index > last) {
      parts.push({ text: text.slice(last, found.index), match: false });
    }

    parts.push({ text: found[0], match: true });
    last = found.index + found[0].length;
  }

  if (last < text.length) {
    parts.push({ text: text.slice(last), match: false });
  }

  return parts;
}

// ============================================================
// MARKDOWN TO PLAIN TEXT
// ============================================================
// Used for reading answers aloud: drops code fences, table rules,
// heading marks and emphasis so the voice reads only the words.
export function stripMarkdown(markdown = "") {
  return markdown
    .replace(/```[\s\S]*?```/g, " Code example omitted. ")
    .replace(/^\s*\|?\s*:?-{2,}.*$/gm, "")
    .replace(/\|/g, ", ")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^\s*[-*•]\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\n{2,}/g, ". ")
    .replace(/\s+/g, " ")
    .trim();
}

// ============================================================
// QUESTIONS FROM SUMMARY KEY POINTS
// ============================================================
// Turns a document's key points into ready-to-ask chat prompts.
export function keyPointQuestions(points, limit = 4) {
  return (Array.isArray(points) ? points : [])
    .filter((point) => typeof point === "string" && point.trim())
    .slice(0, limit)
    .map((point) => {
      const clean = point.trim().replace(/[.:;,]+$/, "");

      return {
        title: clean.length > 60 ? `${clean.slice(0, 57).trim()}...` : clean,
        prompt: `Explain this point from the document in more detail: "${clean}"`,
      };
    });
}
