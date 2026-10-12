// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import Select from "./Select.jsx";
import Markdown from "./Markdown.jsx";
import SourceList from "./SourceList.jsx";
import {
    addChatNote,
    askInChat,
    createChat,
    deleteChat,
    formatMessageTime,
    getChatMessages,
    updateChat,
} from "../api.js";

// ============================================================
// SUGGESTED PROMPTS
// ============================================================
const suggestions = [
    { icon: "sparkles", title: "Summarize", prompt: "Summarize the key points of my documents." },
    { icon: "layers", title: "Important details", prompt: "What are the most important facts, numbers, and dates?" },
    { icon: "check", title: "Action items", prompt: "List any action items, deadlines, or next steps." },
    { icon: "search", title: "Explain simply", prompt: "Explain the main ideas in simple terms." },
];

// ============================================================
// HELPERS
// ============================================================

function parseDate(value) {
    const text = String(value || "");
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`);
}

function groupChats(chats) {
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);
    const day = 86400000;
    const groups = [
        { label: "Today", items: [] },
        { label: "Yesterday", items: [] },
        { label: "Previous 7 days", items: [] },
        { label: "Older", items: [] },
    ];

    for (const chat of chats) {
        const time = parseDate(chat.updated_at).getTime();

        if (time >= startOfToday.getTime()) groups[0].items.push(chat);
        else if (time >= startOfToday.getTime() - day) groups[1].items.push(chat);
        else if (time >= startOfToday.getTime() - 7 * day) groups[2].items.push(chat);
        else groups[3].items.push(chat);
    }

    return groups.filter((group) => group.items.length > 0);
}

// ============================================================
// TYPED ANSWER (WORD-BY-WORD REVEAL)
// ============================================================
// Reveals a fresh answer word by word, like a streaming chatbot.
function TypedAnswer({ text, onProgress, onDone }) {
    const [words] = useState(() => text.split(/(\s+)/));
    const [count, setCount] = useState(0);

    useEffect(() => {
        const step = Math.max(2, Math.ceil(words.length / 120));
        let shown = 0;

        const timer = setInterval(() => {
            shown = Math.min(words.length, shown + step);
            setCount(shown);
            onProgress();

            if (shown >= words.length) {
                clearInterval(timer);
                onDone();
            }
        }, 22);

        return () => clearInterval(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return <Markdown text={words.slice(0, count).join("")} />;
}

// ============================================================
// CONVERSATION (ONE CHAT, OR A NEW ONE BEFORE IT EXISTS)
// ============================================================

function Conversation({
    initialChatId,
    chats,
    documents,
    onChatCreated,
    onChatsChanged,
    onDeleted,
    onOpenDocument,
    onUploadClick,
    onToggleHistory,
}) {
    // ============================================================
    // STATE
    // ============================================================
    const [chatId, setChatId] = useState(initialChatId);
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(Boolean(initialChatId));
    const [sourcesByMessage, setSourcesByMessage] = useState({});
    const [animatingId, setAnimatingId] = useState(null);
    const [question, setQuestion] = useState("");
    const [pendingQuestion, setPendingQuestion] = useState("");
    const [busy, setBusy] = useState("");
    const [error, setError] = useState("");
    const [scope, setScope] = useState("");
    const [renaming, setRenaming] = useState(false);
    const [renameTitle, setRenameTitle] = useState("");
    const [confirmDelete, setConfirmDelete] = useState(false);
    const [copiedId, setCopiedId] = useState(null);

    // ============================================================
    // REFS AND DERIVED VALUES
    // ============================================================
    const scrollRef = useRef(null);
    const inputRef = useRef(null);

    const chat = chats.find((item) => item.id === chatId);
    const readyDocuments = documents.filter((doc) => doc.status === "completed");
    const hasReadyDocuments = readyDocuments.length > 0;
    const showWelcome = !loading && messages.length === 0 && !pendingQuestion;

    // ============================================================
    // SCROLLING
    // ============================================================
    const scrollToBottom = (smooth = true) => {
        const element = scrollRef.current;

        if (element) {
            element.scrollTo({ top: element.scrollHeight, behavior: smooth ? "smooth" : "auto" });
        }
    };

    // ============================================================
    // LOAD MESSAGES AND FOCUS
    // ============================================================
    useEffect(() => {
        if (!initialChatId) {
            return;
        }

        let cancelled = false;

        getChatMessages(initialChatId)
            .then((data) => !cancelled && setMessages(Array.isArray(data) ? data : []))
            .catch((err) => !cancelled && setError(err.message))
            .finally(() => !cancelled && setLoading(false));

        return () => {
            cancelled = true;
        };
    }, [initialChatId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages, pendingQuestion]);

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    // ============================================================
    // COMPOSER INPUT
    // ============================================================
    const resizeInput = () => {
        const element = inputRef.current;

        if (element) {
            element.style.height = "auto";
            element.style.height = `${Math.min(element.scrollHeight, 200)}px`;
        }
    };

    // ============================================================
    // SEND A MESSAGE
    // ============================================================
    // Creates the chat on the first message so "New chat" feels instant.
    const ensureChat = async (text) => {
        if (chatId) {
            return chatId;
        }

        const title = text.length > 60 ? `${text.slice(0, 57).trim()}...` : text;
        const created = await createChat({ title, documentId: scope });
        setChatId(created.id);
        await onChatCreated(created);
        return created.id;
    };

    const send = async (rawText) => {
        const text = (rawText ?? question).trim();

        if (!text || busy) {
            return;
        }

        setBusy("ask");
        setError("");
        setPendingQuestion(text);
        setQuestion("");
        requestAnimationFrame(resizeInput);

        let id = chatId;

        try {
            id = await ensureChat(text);
            const result = await askInChat(id, text);

            setMessages((current) =>
                [...current, result.user_message, result.assistant_message].filter(Boolean)
            );

            if (result.assistant_message?.id) {
                setAnimatingId(result.assistant_message.id);
                setSourcesByMessage((current) => ({
                    ...current,
                    [result.assistant_message.id]: result.sources || [],
                }));
            }

            onChatsChanged();
        } catch (err) {
            setError(err.message);

            // The backend saves the question before answering; re-sync so it is not lost or duplicated.
            const saved = id ? await getChatMessages(id).catch(() => null) : null;

            if (saved) {
                setMessages(saved);
            }

            if (!saved?.some((message) => message.role === "user" && message.content === text)) {
                setQuestion(text);
            }
        } finally {
            setPendingQuestion("");
            setBusy("");
            inputRef.current?.focus();
        }
    };

    // ============================================================
    // SAVE A NOTE
    // ============================================================
    const saveNote = async () => {
        const text = question.trim();

        if (!text || busy) {
            return;
        }

        setBusy("note");
        setError("");

        try {
            const id = await ensureChat(text);
            const message = await addChatNote(id, text);
            setMessages((current) => [...current, message]);
            setQuestion("");
            requestAnimationFrame(resizeInput);
            onChatsChanged();
        } catch (err) {
            setError(err.message);
        } finally {
            setBusy("");
        }
    };

    // ============================================================
    // CHAT SETTINGS (DOCUMENT, RENAME, DELETE)
    // ============================================================
    const changeScope = async (documentId) => {
        if (!chatId) {
            setScope(documentId);
            return;
        }

        // The backend can move a chat to another document, but not unlink it.
        if (!documentId || documentId === chat?.document_id) {
            return;
        }

        try {
            await updateChat(chatId, { documentId });
            await onChatsChanged();
        } catch (err) {
            setError(err.message);
        }
    };

    const rename = async (event) => {
        event.preventDefault();

        try {
            await updateChat(chatId, { title: renameTitle.trim() });
            await onChatsChanged();
            setRenaming(false);
        } catch (err) {
            setError(err.message);
        }
    };

    const remove = async () => {
        try {
            await deleteChat(chatId);
            await onDeleted();
        } catch (err) {
            setError(err.message);
        }
    };

    // ============================================================
    // COPY ANSWER
    // ============================================================
    const copy = async (message) => {
        try {
            await navigator.clipboard.writeText(message.content);
            setCopiedId(message.id);
            setTimeout(() => setCopiedId(null), 1500);
        } catch {
            setError("Copy is not available in this browser.");
        }
    };

    // ============================================================
    // RENDER
    // ============================================================
    const currentScope = chatId ? chat?.document_id || "" : scope;
    const scopeOptions = [
        ...(chatId && chat?.document_id ? [] : [{ value: "", label: "All documents" }]),
        ...readyDocuments.map((doc) => ({ value: doc.id, label: doc.filename })),
    ];

    return (
        <section className="cb-main">
            {/* ============================================================
                CHAT HEADER
                ============================================================ */}
            <header className="cb-header">
                <button
                    className="cb-icon-button cb-history-toggle"
                    onClick={onToggleHistory}
                    title="Chat history"
                >
                    <Icon name="history" size={17} />
                </button>

                {renaming ? (
                    <form className="cb-rename" onSubmit={rename}>
                        <input
                            className="text-input"
                            value={renameTitle}
                            onChange={(event) => setRenameTitle(event.target.value)}
                            maxLength={200}
                            autoFocus
                        />
                        <button className="button button-primary button-small" disabled={!renameTitle.trim()}>
                            Save
                        </button>
                        <button className="button button-small" type="button" onClick={() => setRenaming(false)}>
                            Cancel
                        </button>
                    </form>
                ) : (
                    <div className="cb-title">
                        <h2>{chat?.title || "New chat"}</h2>
                        <div className="cb-scope">
                            <Icon name="link" size={13} />
                            <Select
                                variant="ghost"
                                ariaLabel="Documents this chat answers from"
                                value={currentScope}
                                onChange={changeScope}
                                options={scopeOptions}
                                disabled={!hasReadyDocuments}
                            />
                            {chat?.document_id && (
                                <button className="link-button" onClick={() => onOpenDocument(chat.document_id)}>
                                    Open
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {chatId && !renaming && (
                    <div className="cb-header-actions">
                        {confirmDelete ? (
                            <>
                                <span className="muted">Delete this chat?</span>
                                <button className="button button-danger button-small" onClick={remove}>
                                    Delete
                                </button>
                                <button className="button button-small" onClick={() => setConfirmDelete(false)}>
                                    Cancel
                                </button>
                            </>
                        ) : (
                            <>
                                <button
                                    className="cb-icon-button"
                                    title="Rename chat"
                                    onClick={() => {
                                        setRenameTitle(chat?.title || "");
                                        setRenaming(true);
                                    }}
                                >
                                    <Icon name="pencil" size={15} />
                                </button>
                                <button
                                    className="cb-icon-button cb-icon-danger"
                                    title="Delete chat"
                                    onClick={() => setConfirmDelete(true)}
                                >
                                    <Icon name="trash" size={15} />
                                </button>
                            </>
                        )}
                    </div>
                )}
            </header>

            {/* ============================================================
                MESSAGES AREA
                ============================================================ */}
            <div className="cb-scroll" ref={scrollRef}>
                {loading && (
                    <div className="cb-loading">
                        <span className="spinner" /> Loading conversation...
                    </div>
                )}

                {/* ============================================================
                    WELCOME SCREEN
                    ============================================================ */}
                {showWelcome && (
                    <div className="cb-welcome">
                        <div className="cb-welcome-mark">
                            <Icon name="sparkles" size={56} gradient strokeWidth={1.4} />
                        </div>
                        <h3>How can I help you today?</h3>
                        <p>
                            {hasReadyDocuments
                                ? "Ask anything about your documents. I'll answer from their content and show you the sources."
                                : "Upload a document first, then ask me anything about it."}
                        </p>

                        {hasReadyDocuments ? (
                            <div className="cb-suggestions">
                                {suggestions.map((item) => (
                                    <button
                                        key={item.title}
                                        className="cb-suggestion"
                                        onClick={() => send(item.prompt)}
                                        disabled={Boolean(busy)}
                                    >
                                        <Icon name={item.icon} size={16} />
                                        <strong>{item.title}</strong>
                                        <span>{item.prompt}</span>
                                    </button>
                                ))}
                            </div>
                        ) : (
                            <button className="button button-primary" onClick={onUploadClick}>
                                <Icon name="upload" /> Upload documents
                            </button>
                        )}
                    </div>
                )}

                {/* ============================================================
                    CONVERSATION THREAD
                    ============================================================ */}
                {!showWelcome && (
                    <div className="cb-thread">
                        {messages.map((message) =>
                            message.role === "assistant" ? (
                                <div className="cb-row cb-row-assistant" key={message.id}>
                                    <span className="cb-avatar">
                                        <Icon name="sparkles" size={24} gradient strokeWidth={1.7} />
                                    </span>
                                    <div className="cb-answer">
                                        <div className="cb-answer-name">DocuMind AI</div>
                                        {animatingId === message.id ? (
                                            <TypedAnswer
                                                text={message.content}
                                                onProgress={() => scrollToBottom(false)}
                                                onDone={() => setAnimatingId(null)}
                                            />
                                        ) : (
                                            <Markdown text={message.content} />
                                        )}

                                        {animatingId !== message.id && (
                                            <>
                                                {sourcesByMessage[message.id]?.length > 0 && (
                                                    <details className="cb-sources">
                                                        <summary>
                                                            <Icon name="documents" size={13} />
                                                            {sourcesByMessage[message.id].length}{" "}
                                                            {sourcesByMessage[message.id].length === 1
                                                                ? "source"
                                                                : "sources"}
                                                        </summary>
                                                        <SourceList
                                                            sources={sourcesByMessage[message.id]}
                                                            documents={documents}
                                                            onOpenDocument={onOpenDocument}
                                                            compact
                                                        />
                                                    </details>
                                                )}
                                                <div className="cb-answer-actions">
                                                    <button onClick={() => copy(message)} title="Copy answer">
                                                        <Icon name={copiedId === message.id ? "checkMark" : "copy"} size={13} />
                                                        {copiedId === message.id ? "Copied" : "Copy"}
                                                    </button>
                                                    <span>{formatMessageTime(message.created_at)}</span>
                                                </div>
                                            </>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <div className="cb-row cb-row-user" key={message.id}>
                                    <div className="cb-bubble">{message.content}</div>
                                    <span className="cb-time">{formatMessageTime(message.created_at)}</span>
                                </div>
                            )
                        )}

                        {pendingQuestion && (
                            <>
                                <div className="cb-row cb-row-user">
                                    <div className="cb-bubble">{pendingQuestion}</div>
                                </div>
                                <div className="cb-row cb-row-assistant">
                                    <span className="cb-avatar">
                                        <Icon name="sparkles" size={24} gradient strokeWidth={1.7} />
                                    </span>
                                    <div className="cb-answer">
                                        <div className="cb-answer-name">DocuMind AI</div>
                                        <div className="cb-typing" aria-label="DocuMind AI is thinking">
                                            <span />
                                            <span />
                                            <span />
                                        </div>
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                )}
            </div>

            {/* ============================================================
                COMPOSER
                ============================================================ */}
            <div className="cb-composer-wrap">
                {error && (
                    <div className="notice notice-error cb-error" role="alert">
                        <span>{error}</span>
                        <button className="notice-close" onClick={() => setError("")}>
                            <Icon name="close" size={14} />
                        </button>
                    </div>
                )}

                <form
                    className="cb-composer"
                    onSubmit={(event) => {
                        event.preventDefault();
                        send();
                    }}
                >
                    <button
                        type="button"
                        className="cb-icon-button"
                        onClick={onUploadClick}
                        title="Upload documents"
                    >
                        <Icon name="paperclip" size={17} />
                    </button>
                    <textarea
                        ref={inputRef}
                        rows={1}
                        value={question}
                        onChange={(event) => {
                            setQuestion(event.target.value);
                            resizeInput();
                        }}
                        onKeyDown={(event) => {
                            if (event.key === "Enter" && !event.shiftKey) {
                                event.preventDefault();
                                send();
                            }
                        }}
                        placeholder={
                            hasReadyDocuments ? "Message DocuMind AI..." : "Upload a document to start chatting"
                        }
                        maxLength={5000}
                        disabled={!hasReadyDocuments || busy === "ask"}
                    />
                    <button
                        type="button"
                        className="cb-icon-button"
                        onClick={saveNote}
                        disabled={!question.trim() || Boolean(busy)}
                        title="Save as a note (no AI answer)"
                    >
                        <Icon name="note" size={17} />
                    </button>
                    <button
                        type="submit"
                        className="cb-send"
                        disabled={!question.trim() || Boolean(busy)}
                        title="Send"
                    >
                        {busy === "ask" ? <span className="spinner spinner-light" /> : <Icon name="arrowUp" size={18} />}
                    </button>
                </form>
                <div className="cb-hint">
                    Answers come from your documents. <kbd>Enter</kbd> to send · <kbd>Shift</kbd> +{" "}
                    <kbd>Enter</kbd> for a new line
                </div>
            </div>
        </section>
    );
}

// ============================================================
// CHAT PAGE: HISTORY SIDEBAR + CONVERSATION
// ============================================================

function ChatView({
    chats,
    documents,
    activeChatId,
    onSelectChat,
    onChatsChanged,
    onOpenDocument,
    onUploadClick,
}) {
    // ============================================================
    // STATE
    // ============================================================
    // The conversation remounts only when the user switches chats, so a
    // chat created from the "New chat" screen keeps its in-progress state.
    const [conversationKey, setConversationKey] = useState(() => activeChatId || `new-${Date.now()}`);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [filter, setFilter] = useState("");

    const documentNames = Object.fromEntries(documents.map((doc) => [doc.id, doc.filename]));
    const visibleChats = chats.filter((chat) =>
        chat.title.toLowerCase().includes(filter.trim().toLowerCase())
    );

    // ============================================================
    // OPEN A CHAT
    // ============================================================
    const openChat = (chatId) => {
        onSelectChat(chatId);
        setConversationKey(chatId || `new-${Date.now()}`);
        setHistoryOpen(false);
    };

    return (
        <div className={`cb-layout ${historyOpen ? "history-open" : ""}`}>
            {/* ============================================================
                CHAT HISTORY SIDEBAR
                ============================================================ */}
            <aside className="cb-history">
                <button className="button button-primary cb-new" onClick={() => openChat(null)}>
                    <Icon name="plus" /> New chat
                </button>

                <div className="filter-field cb-filter">
                    <Icon name="search" size={14} />
                    <input
                        value={filter}
                        onChange={(event) => setFilter(event.target.value)}
                        placeholder="Search chats..."
                    />
                </div>

                <div className="cb-history-list">
                    {groupChats(visibleChats).map((group) => (
                        <div key={group.label} className="cb-history-group">
                            <div className="cb-history-label">{group.label}</div>
                            {group.items.map((chat) => (
                                <button
                                    key={chat.id}
                                    className={`cb-history-item ${chat.id === activeChatId ? "active" : ""}`}
                                    onClick={() => openChat(chat.id)}
                                >
                                    <Icon name="chat" size={14} />
                                    <span>
                                        <strong>{chat.title}</strong>
                                        <small>
                                            {chat.document_id
                                                ? documentNames[chat.document_id] || "Linked document"
                                                : "All documents"}
                                        </small>
                                    </span>
                                </button>
                            ))}
                        </div>
                    ))}

                    {visibleChats.length === 0 && (
                        <p className="cb-history-empty">
                            {chats.length === 0 ? "Your conversations will appear here." : "No chats match your search."}
                        </p>
                    )}
                </div>
            </aside>

            {/* ============================================================
                MOBILE DRAWER BACKDROP
                ============================================================ */}
            {historyOpen && <div className="cb-scrim" onClick={() => setHistoryOpen(false)} />}

            {/* ============================================================
                CONVERSATION
                ============================================================ */}
            <Conversation
                key={conversationKey}
                initialChatId={conversationKey.startsWith("new-") ? null : conversationKey}
                chats={chats}
                documents={documents}
                onChatCreated={async (chat) => {
                    onSelectChat(chat.id);
                    await onChatsChanged();
                }}
                onChatsChanged={onChatsChanged}
                onDeleted={async () => {
                    await onChatsChanged();
                    openChat(null);
                }}
                onOpenDocument={onOpenDocument}
                onUploadClick={onUploadClick}
                onToggleHistory={() => setHistoryOpen((open) => !open)}
            />
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default ChatView;
