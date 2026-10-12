// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import { askDocuments, formatFileSize, formatRelativeTime } from "../api.js";
import Icon from "./Icons.jsx";
import { FileIcon, StatusBadge } from "./DocumentBadges.jsx";
import SourceList from "./SourceList.jsx";

// ============================================================
// DASHBOARD OVERVIEW
// ============================================================
function Overview({
    documents,
    chats,
    loading,
    onUploadClick,
    onOpenDocument,
    onOpenChat,
    onNewChat,
    onSearch,
    onNavigate,
}) {
    // ============================================================
    // STATE
    // ============================================================
    const [question, setQuestion] = useState("");
    const [asking, setAsking] = useState(false);
    const [answer, setAnswer] = useState(null);
    const [error, setError] = useState("");

    // ============================================================
    // DERIVED VALUES
    // ============================================================
    const readyDocuments = documents.filter((doc) => doc.status === "completed");
    const failedCount = documents.filter((doc) => doc.status === "failed").length;
    const pageCount = readyDocuments.reduce((total, doc) => total + (doc.page_count || 0), 0);
    const wordCount = readyDocuments.reduce((total, doc) => total + (doc.word_count || 0), 0);
    const documentNames = Object.fromEntries(documents.map((doc) => [doc.id, doc.filename]));
    const hasDocuments = documents.length > 0;

    // ============================================================
    // ASK AI
    // ============================================================
    const handleAsk = async (event) => {
        event.preventDefault();

        const text = question.trim();

        if (!text) {
            return;
        }

        setAsking(true);
        setError("");
        setAnswer(null);

        try {
            setAnswer(await askDocuments(text));
        } catch (err) {
            setError(err.message);
        } finally {
            setAsking(false);
        }
    };

    // ============================================================
    // STAT CARDS
    // ============================================================
    const stats = [
        {
            label: "Documents",
            value: documents.length,
            icon: "documents",
            footnote: "In this workspace",
        },
        {
            label: "Ready for AI",
            value: readyDocuments.length,
            icon: "check",
            footnote: failedCount > 0 ? `${failedCount} failed to process` : "Searchable and chat-ready",
            warning: failedCount > 0,
        },
        {
            label: "Pages indexed",
            value: pageCount.toLocaleString(),
            icon: "layers",
            footnote: `${wordCount.toLocaleString()} words`,
        },
        {
            label: "Conversations",
            value: chats.length,
            icon: "chat",
            footnote: "Chat sessions",
        },
    ];

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <>
            {/* ============================================================
                STATISTICS
                ============================================================ */}
            <div className="stats-grid stats-grid-4">
                {stats.map((stat) => (
                    <div className="panel stat-card" key={stat.label}>
                        <div className="stat-icon">
                            <Icon name={stat.icon} size={18} />
                        </div>
                        <div className="stat-label">{stat.label}</div>
                        <div className="stat-number">{loading ? "–" : stat.value}</div>
                        <div className={`stat-footnote ${stat.warning ? "stat-warning" : ""}`}>
                            {stat.footnote}
                        </div>
                    </div>
                ))}
            </div>

            {/* ============================================================
                ASK YOUR DOCUMENTS
                ============================================================ */}
            <div className="panel ask-panel">
                <div className="section-title">
                    <Icon name="sparkles" size={16} className="title-icon" />
                    Ask your documents
                </div>
                <p className="muted">
                    Get an AI answer drawn from everything you have uploaded, with the sources it used.
                </p>

                <form className="search-form" onSubmit={handleAsk}>
                    <Icon name="sparkles" size={18} className="search-icon" />
                    <input
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        placeholder={
                            hasDocuments
                                ? "e.g. What are the key deadlines in my contracts?"
                                : "Upload a document to start asking questions"
                        }
                        maxLength={5000}
                        disabled={!readyDocuments.length}
                    />
                    <button
                        className="button"
                        type="button"
                        disabled={!question.trim() || asking}
                        onClick={() => onSearch(question.trim())}
                    >
                        <Icon name="search" /> Find passages
                    </button>
                    <button
                        className="button button-primary"
                        type="submit"
                        disabled={!question.trim() || asking}
                    >
                        {asking ? <span className="spinner spinner-light" /> : <Icon name="send" />}
                        {asking ? "Thinking..." : "Ask AI"}
                    </button>
                </form>

                {error && <div className="notice notice-error ask-result">{error}</div>}

                {/* ============================================================
                    AI ANSWER
                    ============================================================ */}
                {answer && (
                    <div className="ask-result">
                        <div className="answer-card">
                            <div className="sub-heading">AI ANSWER</div>
                            <p className="answer-text">{answer.answer}</p>
                        </div>
                        {answer.sources?.length > 0 && (
                            <details className="chat-sources">
                                <summary>
                                    {answer.sources.length}{" "}
                                    {answer.sources.length === 1 ? "source" : "sources"}
                                </summary>
                                <SourceList
                                    sources={answer.sources}
                                    documents={documents}
                                    onOpenDocument={onOpenDocument}
                                    compact
                                />
                            </details>
                        )}
                    </div>
                )}
            </div>

            {/* ============================================================
                RECENT ACTIVITY
                ============================================================ */}
            <div className="overview-grid">
                {/* ============================================================
                    RECENT DOCUMENTS
                    ============================================================ */}
                <div className="panel">
                    <div className="panel-header">
                        <div>
                            <h2>Recent documents</h2>
                            <p className="muted">Your latest uploads</p>
                        </div>
                        {hasDocuments && (
                            <button className="link-button" onClick={() => onNavigate("Documents")}>
                                View all <Icon name="arrowRight" size={14} />
                            </button>
                        )}
                    </div>

                    {loading ? (
                        <div className="empty-state">Loading documents...</div>
                    ) : hasDocuments ? (
                        <div className="compact-list">
                            {documents.slice(0, 5).map((doc) => (
                                <button
                                    className="compact-row"
                                    key={doc.id}
                                    onClick={() => onOpenDocument(doc.id)}
                                >
                                    <FileIcon filename={doc.filename} />
                                    <span className="compact-text">
                                        <strong>{doc.filename}</strong>
                                        <span>
                                            {formatFileSize(doc.file_size)}
                                            {doc.page_count ? ` · ${doc.page_count} ${doc.page_count === 1 ? "page" : "pages"}` : ""}
                                            {" · "}
                                            {formatRelativeTime(doc.created_at)}
                                        </span>
                                    </span>
                                    <StatusBadge status={doc.status} />
                                </button>
                            ))}
                        </div>
                    ) : (
                        <button className="dropzone" onClick={onUploadClick}>
                            <span className="empty-icon">
                                <Icon name="upload" size={22} />
                            </span>
                            <strong>Upload your first document</strong>
                            <span>Drag files here or click to browse</span>
                            <span className="file-types">PDF · DOCX · TXT · CSV · XLSX · PPTX · PNG · JPG — up to 10 MB</span>
                        </button>
                    )}
                </div>

                {/* ============================================================
                    RECENT CONVERSATIONS
                    ============================================================ */}
                <div className="panel">
                    <div className="panel-header">
                        <div>
                            <h2>Recent conversations</h2>
                            <p className="muted">Pick up where you left off</p>
                        </div>
                        {readyDocuments.length > 0 && (
                            <button className="button button-small" onClick={onNewChat}>
                                <Icon name="plus" /> New chat
                            </button>
                        )}
                    </div>

                    {chats.length > 0 ? (
                        <div className="compact-list">
                            {chats.slice(0, 5).map((chat) => (
                                <button
                                    className="compact-row"
                                    key={chat.id}
                                    onClick={() => onOpenChat(chat.id)}
                                >
                                    <span className="row-icon">
                                        <Icon name="chat" size={16} />
                                    </span>
                                    <span className="compact-text">
                                        <strong>{chat.title}</strong>
                                        <span>
                                            {chat.document_id
                                                ? documentNames[chat.document_id] || "Linked document"
                                                : "All documents"}
                                        </span>
                                    </span>
                                    <span className="row-time">
                                        {formatRelativeTime(chat.updated_at)}
                                    </span>
                                </button>
                            ))}
                        </div>
                    ) : (
                        <div className="empty-state">
                            <div className="empty-icon">
                                <Icon name="chat" size={22} />
                            </div>
                            <strong>No conversations yet</strong>
                            <span>
                                {readyDocuments.length
                                    ? "Start a chat to ask follow-up questions about your documents."
                                    : "Upload a document first, then chat with it here."}
                            </span>
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Overview;
