// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import Icon from "./Icons.jsx";
import SourcePreview from "./SourcePreview.jsx";

// ============================================================
// CONFIGURATION
// ============================================================
const LONG_TEXT = 320;

// ============================================================
// SOURCE LIST (SEARCH RESULTS AND AI SOURCES)
// ============================================================
// `highlight` is the search query or question; its words are highlighted
// when a passage is opened in the preview.
function SourceList({ sources, documents, onOpenDocument, compact = false, highlight = "" }) {
    const [expanded, setExpanded] = useState({});
    const [previewIndex, setPreviewIndex] = useState(null);

    if (!Array.isArray(sources) || sources.length === 0) {
        return null;
    }

    const names = Object.fromEntries(documents.map((doc) => [doc.id, doc.filename]));

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className={`source-list ${compact ? "source-list-compact" : ""}`}>
            {sources.map((source, index) => {
                const text = (source.text || "").trim();
                const key = source.chunk_id || index;
                const isLong = !compact && text.length > LONG_TEXT;
                const isOpen = Boolean(expanded[key]);
                const score = typeof source.score === "number" ? Math.round(source.score * 100) : null;

                return (
                    <div className="source-item" key={key}>
                        <div className="source-meta">
                            <button
                                className="link-button"
                                onClick={() => onOpenDocument(source.document_id)}
                                disabled={!names[source.document_id]}
                            >
                                {names[source.document_id] || "Document"}
                            </button>
                            {source.page_number != null && <span>Page {source.page_number}</span>}
                            {score !== null && (
                                <span
                                    className="score-pill"
                                    title={[
                                        typeof source.semantic_score === "number" &&
                                            `Meaning ${Math.round(source.semantic_score * 100)}%`,
                                        typeof source.keyword_score === "number" &&
                                            `Keywords ${Math.round(source.keyword_score * 100)}%`,
                                    ]
                                        .filter(Boolean)
                                        .join(" · ")}
                                >
                                    {score}% match
                                </span>
                            )}
                            {(source.is_neighbor || source.contextual_boost > 0) && (
                                <span className="context-tag">Nearby context</span>
                            )}
                            {text && (
                                <button
                                    className="link-button source-view"
                                    onClick={() => setPreviewIndex(index)}
                                    title="Read the full passage"
                                >
                                    <Icon name="eye" size={13} /> View passage
                                </button>
                            )}
                        </div>
                        {text && (
                            <p className={`source-text ${isLong && !isOpen ? "is-clamped" : ""}`}>
                                {compact && text.length > 280 ? `${text.slice(0, 280)}…` : text}
                            </p>
                        )}

                        {/* ============================================================
                            SHOW MORE / SHOW LESS
                            ============================================================ */}
                        {isLong && (
                            <button
                                className="link-button source-toggle"
                                onClick={() => setExpanded((current) => ({ ...current, [key]: !isOpen }))}
                            >
                                {isOpen ? "Show less" : "Show more"}
                            </button>
                        )}
                    </div>
                );
            })}

            {/* ============================================================
                PASSAGE PREVIEW
                ============================================================ */}
            {previewIndex !== null && sources[previewIndex] && (
                <SourcePreview
                    source={sources[previewIndex]}
                    documentName={names[sources[previewIndex].document_id]}
                    document={documents.find((doc) => doc.id === sources[previewIndex].document_id)}
                    highlight={highlight}
                    onClose={() => setPreviewIndex(null)}
                    onOpenDocument={onOpenDocument}
                />
            )}
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default SourceList;
