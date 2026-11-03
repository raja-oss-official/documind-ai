// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import Icon from "./Icons.jsx";
import Modal from "./Modal.jsx";
import DocumentPreview from "./DocumentPreview.jsx";
import { fileExtension } from "../api.js";
import { queryTerms, splitByTerms } from "../text.js";

// ============================================================
// SOURCE PREVIEW (FULL PASSAGE WITH HIGHLIGHTED TERMS)
// ============================================================
// Shows the exact passage an answer or search result came from, with
// the words from the question highlighted, so it is easy to verify.
function SourcePreview({ source, document, documentName, highlight, onClose, onOpenDocument }) {
    const [showOriginal, setShowOriginal] = useState(false);

    const terms = queryTerms(highlight);
    const parts = splitByTerms((source.text || "").trim(), terms);
    const percent = (value) => (typeof value === "number" ? `${Math.round(value * 100)}%` : null);
    const scores = [
        ["Match", percent(source.score)],
        ["Meaning", percent(source.semantic_score)],
        ["Keywords", percent(source.keyword_score)],
    ].filter(([, value]) => value);

    // ============================================================
    // ORIGINAL FILE AT THE CITED PAGE
    // ============================================================
    // Replaces this dialog (one dialog at a time keeps Escape simple).
    if (showOriginal && document) {
        return (
            <DocumentPreview
                document={document}
                page={fileExtension(document.filename) === ".pdf" ? source.page_number : null}
                passage={(source.text || "").trim()}
                onClose={onClose}
            />
        );
    }

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <Modal
            title={documentName || "Document"}
            subtitle={[
                source.page_number != null && `Page ${source.page_number}`,
                source.chunk_index != null && `Passage ${source.chunk_index + 1}`,
            ]
                .filter(Boolean)
                .join(" · ")}
            onClose={onClose}
            footer={
                <>
                    <span className="muted">
                        {terms.length > 0 ? "Highlighted words come from your question." : "Exact text from your document."}
                    </span>
                    {document && (
                        <button className="button button-small" onClick={() => setShowOriginal(true)}>
                            <Icon name="eye" />{" "}
                            {fileExtension(document.filename) === ".pdf" && source.page_number != null
                                ? `Open original at page ${source.page_number}`
                                : "Open original"}
                        </button>
                    )}
                    {documentName && (
                        <button
                            className="button button-primary button-small"
                            onClick={() => {
                                onClose();
                                onOpenDocument(source.document_id);
                            }}
                        >
                            <Icon name="documents" /> Open document
                        </button>
                    )}
                </>
            }
        >
            {scores.length > 0 && (
                <div className="preview-scores">
                    {scores.map(([label, value]) => (
                        <div key={label}>
                            <span>{label}</span>
                            <strong>{value}</strong>
                        </div>
                    ))}
                </div>
            )}

            <p className="preview-text">
                {parts.map((part, index) => (part.match ? <mark key={index}>{part.text}</mark> : part.text))}
            </p>
        </Modal>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default SourcePreview;
