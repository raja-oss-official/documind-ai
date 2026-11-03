// ============================================================
// IMPORTS
// ============================================================
import { fileExtension } from "../api.js";

// ============================================================
// STATUS LABELS
// ============================================================
const statusLabels = {
    completed: "Processed",
    processing: "Processing",
    failed: "Failed",
    uploaded: "Uploaded",
};

// ============================================================
// STATUS BADGE
// ============================================================
export function StatusBadge({ status }) {
    const variant =
        status === "completed"
            ? "badge-success"
            : status === "failed"
                ? "badge-danger"
                : "badge-neutral";

    return <span className={`badge ${variant}`}>{statusLabels[status] || status}</span>;
}

// ============================================================
// FILE TYPE ICON
// ============================================================
// `video` shows a YouTube badge (videos have a title, not a filename).
export function FileIcon({ filename, video = false }) {
    const extension = video ? "YT" : fileExtension(filename).replace(".", "").toUpperCase() || "FILE";

    return <div className={`file-icon file-icon-${extension.toLowerCase()}`}>{extension}</div>;
}
