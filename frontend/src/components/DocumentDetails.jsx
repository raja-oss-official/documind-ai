// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import Icon from "./Icons.jsx";
import {
    createChat,
    deleteDocument,
    formatDate,
    formatFileSize,
    generateSummary,
    renameDocument,
} from "../api.js";
import { FileIcon, StatusBadge } from "./DocumentBadges.jsx";

// ============================================================
// PROCESSING TYPE LABELS
// ============================================================
const processingLabels = {
    text_pdf: "Text PDF",
    ocr_pdf: "Scanned PDF (OCR)",
    docx: "Word document",
    txt: "Plain text",
    csv: "CSV",
    xlsx: "Excel spreadsheet",
    pptx: "PowerPoint",
    image_ocr: "Image (OCR)",
};

// ============================================================
// DOCUMENT DETAILS
// ============================================================
function DocumentDetails({ document, onBack, onChanged, onDeleted, onSearch, onChatCreated }) {
    // ============================================================
    // STATE
    // ============================================================
    const [renaming, setRenaming] = useState(false);
    const [newName, setNewName] = useState(document.filename || "");
    const [busy, setBusy] = useState("");
    const [error, setError] = useState("");
    const [confirmDelete, setConfirmDelete] = useState(false);

    const isReady = document.status === "completed";
    const keyPoints = Array.isArray(document.key_points) ? document.key_points : [];

    // ============================================================
    // ACTIONS (RENAME, SUMMARY, DELETE, CHAT)
    // ============================================================
    const run = async (label, action) => {
        setBusy(label);
        setError("");

        try {
            await action();
        } catch (err) {
            setError(err.message);
        } finally {
            setBusy("");
        }
    };

    const handleRename = (event) => {
        event.preventDefault();

        run("rename", async () => {
            await renameDocument(document.id, newName.trim());
            await onChanged();
            setRenaming(false);
        });
    };

    const handleSummary = () =>
        run("summary", async () => {
            await generateSummary(document.id);
            await onChanged();
        });

    const handleDelete = () =>
        run("delete", async () => {
            await deleteDocument(document.id);
            onDeleted();
        });

    const handleChat = () =>
        run("chat", async () => {
            const title = document.filename.replace(/\.[^.]+$/, "").slice(0, 200);
            const chat = await createChat({ title, documentId: document.id });
            await onChatCreated(chat);
        });

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="panel details-panel">
            {/* ============================================================
                HEADER AND RENAME
                ============================================================ */}
            <div className="panel-header">
                <div className="document-name">
                    <FileIcon filename={document.filename} />
                    {renaming ? (
                        <form className="inline-form" onSubmit={handleRename}>
                            <input
                                className="text-input"
                                value={newName}
                                onChange={(event) => setNewName(event.target.value)}
                                maxLength={255}
                                autoFocus
                            />
                            <button
                                className="button button-primary"
                                type="submit"
                                disabled={!newName.trim() || busy === "rename"}
                            >
                                {busy === "rename" ? "Saving..." : "Save"}
                            </button>
                            <button
                                className="button"
                                type="button"
                                onClick={() => {
                                    setRenaming(false);
                                    setNewName(document.filename);
                                }}
                            >
                                Cancel
                            </button>
                        </form>
                    ) : (
                        <div>
                            <h2>{document.filename}</h2>
                            <p className="muted">Uploaded {formatDate(document.created_at)}</p>
                        </div>
                    )}
                </div>
                <button className="button" onClick={onBack}>
                    <Icon name="arrowLeft" /> All documents
                </button>
            </div>

            {/* ============================================================
                DETAILS BODY
                ============================================================ */}
            <div className="details-body">
                {error && (
                    <div className="notice notice-error" role="alert">
                        {error}
                    </div>
                )}

                {/* ============================================================
                    STATISTICS
                    ============================================================ */}
                <div className="details-stats">
                    <div>
                        <span>Status</span>
                        <StatusBadge status={document.status} />
                    </div>
                    <div>
                        <span>Type</span>
                        <strong>
                            {processingLabels[document.processing_type] ||
                                document.processing_type ||
                                "—"}
                        </strong>
                    </div>
                    <div>
                        <span>Size</span>
                        <strong>{formatFileSize(document.file_size)}</strong>
                    </div>
                    <div>
                        <span>Pages</span>
                        <strong>{document.page_count || 0}</strong>
                    </div>
                    <div>
                        <span>Words</span>
                        <strong>{(document.word_count || 0).toLocaleString()}</strong>
                    </div>
                    <div>
                        <span>Characters</span>
                        <strong>{(document.character_count || 0).toLocaleString()}</strong>
                    </div>
                    <div>
                        <span>Chunks</span>
                        <strong>{document.chunk_count || 0}</strong>
                    </div>
                </div>

                {document.processing_error && (
                    <div className="notice notice-error">
                        Processing error: {document.processing_error}
                    </div>
                )}

                {/* ============================================================
                    ACTION BUTTONS
                    ============================================================ */}
                <div className="action-row">
                    <button
                        className="button button-primary"
                        onClick={handleChat}
                        disabled={!isReady || Boolean(busy)}
                    >
                        {busy === "chat" ? "Creating chat..." : <><Icon name="chat" /> Chat with this document</>}
                    </button>
                    <button
                        className="button"
                        onClick={() => onSearch(document.id)}
                        disabled={!isReady}
                    >
                        <Icon name="search" /> Search in document
                    </button>
                    <button
                        className="button"
                        onClick={() => setRenaming(true)}
                        disabled={renaming || Boolean(busy)}
                    >
                        <Icon name="pencil" /> Rename
                    </button>
                    {confirmDelete ? (
                        <span className="confirm-group">
                            <span className="muted">Delete permanently?</span>
                            <button
                                className="button button-danger"
                                onClick={handleDelete}
                                disabled={Boolean(busy)}
                            >
                                {busy === "delete" ? "Deleting..." : "Yes, delete"}
                            </button>
                            <button className="button" onClick={() => setConfirmDelete(false)}>
                                Cancel
                            </button>
                        </span>
                    ) : (
                        <button
                            className="button button-danger-outline"
                            onClick={() => setConfirmDelete(true)}
                            disabled={Boolean(busy)}
                        >
                            <Icon name="trash" /> Delete
                        </button>
                    )}
                </div>

                {/* ============================================================
                    AI SUMMARY
                    ============================================================ */}
                <div className="summary-section">
                    <div className="summary-heading">
                        <div>
                            <div className="section-title">
                                <Icon name="sparkles" size={16} className="title-icon" />
                                AI summary
                            </div>
                            {document.summary_generated_at && (
                                <p className="muted">
                                    Generated {formatDate(document.summary_generated_at)}
                                    {document.summary_method && ` · ${document.summary_method} method`}
                                </p>
                            )}
                        </div>
                        <button
                            className="button"
                            onClick={handleSummary}
                            disabled={!isReady || Boolean(busy)}
                        >
                            {busy === "summary"
                                ? "Generating..."
                                : document.summary
                                    ? "Regenerate summary"
                                    : "Generate summary"}
                        </button>
                    </div>

                    {busy === "summary" && (
                        <p className="muted">
                            <span className="spinner" /> Reading the document and writing a
                            summary. Large documents can take a minute.
                        </p>
                    )}

                    {document.summary ? (
                        <>
                            <p className="summary-text">{document.summary}</p>
                            {keyPoints.length > 0 && (
                                <>
                                    <div className="sub-heading">KEY POINTS</div>
                                    <ul className="key-points">
                                        {keyPoints.map((point, index) => (
                                            <li key={index}>
                                                {typeof point === "string"
                                                    ? point
                                                    : JSON.stringify(point)}
                                            </li>
                                        ))}
                                    </ul>
                                </>
                            )}
                        </>
                    ) : (
                        busy !== "summary" && (
                            <p className="muted">
                                {isReady
                                    ? "No summary yet. Generate one to see the key points of this document."
                                    : "Summaries are available once the document has been processed."}
                            </p>
                        )
                    )}
                </div>
            </div>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default DocumentDetails;
