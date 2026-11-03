// ============================================================
// IMPORTS
// ============================================================
import Icon from "./Icons.jsx";
import Modal from "./Modal.jsx";
import { queryTerms, splitByTerms } from "../text.js";

// ============================================================
// SOURCE PREVIEW (FULL PASSAGE WITH HIGHLIGHTED TERMS)
// ============================================================
// Shows the exact passage an answer or search result came from, with
// the words from the question highlighted, so it is easy to verify.
function SourcePreview({ source, documentName, highlight, onClose, onOpenDocument }) {
    const terms = queryTerms(highlight);
    const parts = splitByTerms((source.text || "").trim(), terms);
    const percent = (value) => (typeof value === "number" ? `${Math.round(value * 100)}%` : null);
    const scores = [
        ["Match", percent(source.score)],
        ["Meaning", percent(source.semantic_score)],
        ["Keywords", percent(source.keyword_score)],
    ].filter(([, value]) => value);

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
