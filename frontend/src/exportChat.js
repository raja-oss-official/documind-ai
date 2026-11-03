// ============================================================
// CHAT EXPORT (MARKDOWN DOWNLOAD)
// ============================================================
import { formatDate } from "./api.js";

// ============================================================
// BUILD MARKDOWN
// ============================================================
export function chatToMarkdown({ title, scopeLabel, messages, sourcesByMessage = {}, documentNames = {} }) {
  const lines = [
    `# ${title || "DocuMind AI chat"}`,
    "",
    `_Exported from DocuMind AI on ${new Date().toLocaleString()} · Answers from: ${scopeLabel}_`,
    "",
  ];

  for (const message of messages) {
    const time = formatDate(message.created_at);

    if (message.role === "assistant") {
      lines.push(`## DocuMind AI${time ? ` · ${time}` : ""}`, "", message.content.trim(), "");

      const sources = sourcesByMessage[message.id] || [];

      if (sources.length > 0) {
        lines.push("**Sources**", "");

        for (const source of sources) {
          const name = documentNames[source.document_id] || "Document";
          const page = source.page_number != null ? `, page ${source.page_number}` : "";
          lines.push(`- ${name}${page}`);
        }

        lines.push("");
      }
    } else {
      // A blockquote keeps the user's text visually separate from answers.
      const quoted = message.content
        .trim()
        .split("\n")
        .map((line) => `> ${line}`)
        .join("\n");
      lines.push(`## You${time ? ` · ${time}` : ""}`, "", quoted, "");
    }
  }

  return lines.join("\n");
}

// ============================================================
// DOWNLOAD A TEXT FILE
// ============================================================
export function downloadTextFile(filename, text, type = "text/markdown") {
  const url = URL.createObjectURL(new Blob([text], { type: `${type};charset=utf-8` }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function safeFilename(name, extension) {
  const base = (name || "documind-chat")
    .replace(/[^a-z0-9 _-]+/gi, "")
    .trim()
    .replace(/\s+/g, "-")
    .slice(0, 80);

  return `${base || "documind-chat"}.${extension}`;
}
