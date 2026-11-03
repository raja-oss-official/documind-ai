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
    askInChatStream,
    createChat,
    deleteChat,
    formatMessageTime,
    getChatMessages,
    getSharedChatMessages,
    listChatShares,
    removeChatShare,
    shareChat,
    updateChat,
} from "../api.js";
import ShareDialog from "./ShareDialog.jsx";
import { readJSON, userKey, writeJSON } from "../storage.js";
import { keyPointQuestions, stripMarkdown } from "../text.js";
import { readAloudSupported, speak, startDictation, stopSpeaking, voiceInputSupported } from "../speech.js";
import { chatToMarkdown, downloadTextFile, safeFilename } from "../exportChat.js";

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

// The backend does not store sources with messages, so the sources of
// answers given in this browser are kept locally (trimmed to fit).
const MAX_SAVED_ANSWERS = 30;
const MAX_SAVED_SOURCE_TEXT = 1200;

const sourcesKey = (userId, chatId) => userKey(userId, `sources_${chatId}`);

function trimSources(sourcesByMessage) {
    return Object.fromEntries(
        Object.entries(sourcesByMessage)
            .slice(-MAX_SAVED_ANSWERS)
            .map(([messageId, sources]) => [
                messageId,
                sources.map((source) => ({ ...source, text: (source.text || "").slice(0, MAX_SAVED_SOURCE_TEXT) })),
            ])
    );
}

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
    sharedChat,
    userId,
    pendingPrompt,
    onPromptConsumed,
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
    const [sourcesByMessage, setSourcesByMessage] = useState(() =>
        initialChatId ? readJSON(sourcesKey(userId, initialChatId), {}) : {}
    );
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
    const [listening, setListening] = useState(false);
    const [speakingId, setSpeakingId] = useState(null);
    const [streamText, setStreamText] = useState(null);
    const [showShare, setShowShare] = useState(false);

    // ============================================================
    // REFS AND DERIVED VALUES
    // ============================================================
    const scrollRef = useRef(null);
    const inputRef = useRef(null);
    const stopDictationRef = useRef(null);
    const handledPromptRef = useRef(false);

    // A chat shared by another user opens read-only.
    const readOnly = Boolean(sharedChat);
    const chat = sharedChat || chats.find((item) => item.id === chatId);
    const readyDocuments = documents.filter((doc) => doc.status === "completed");
    const hasReadyDocuments = readyDocuments.length > 0;
    const showWelcome = !loading && messages.length === 0 && !pendingQuestion;
    const documentNames = Object.fromEntries(documents.map((doc) => [doc.id, doc.filename]));

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

        const loadMessages = readOnly ? getSharedChatMessages : getChatMessages;

        loadMessages(initialChatId)
            .then((data) => {
                if (cancelled) return;

                const list = Array.isArray(data) ? data : [];
                setMessages(list);

                // Sources saved with messages by the backend; older answers
                // fall back to the copy kept in this browser.
                const saved = Object.fromEntries(
                    list.filter((message) => message.sources?.length).map((message) => [message.id, message.sources])
                );
                setSourcesByMessage((current) => ({ ...current, ...saved }));
            })
            .catch((err) => !cancelled && setError(err.message))
            .finally(() => !cancelled && setLoading(false));

        return () => {
            cancelled = true;
        };
    }, [initialChatId, readOnly]);

    useEffect(() => {
        scrollToBottom(streamText === null);
    }, [messages, pendingQuestion, streamText]);

    useEffect(() => {
        inputRef.current?.focus();

        // Stop the microphone and any reading when leaving the chat.
        return () => {
            stopDictationRef.current?.();
            stopSpeaking();
        };
    }, []);

    // ============================================================
    // REMEMBER ANSWER SOURCES IN THIS BROWSER
    // ============================================================
    useEffect(() => {
        if (chatId && !readOnly && Object.keys(sourcesByMessage).length > 0) {
            writeJSON(sourcesKey(userId, chatId), trimSources(sourcesByMessage));
        }
    }, [chatId, readOnly, sourcesByMessage, userId]);


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
            let started = false;

            try {
                // The answer streams in as Gemini writes it.
                await askInChatStream(id, text, (name, data) => {
                    if (name === "start") {
                        started = true;
                        setPendingQuestion("");
                        setMessages((current) => [...current, data.user_message]);
                        setStreamText("");
                    } else if (name === "token") {
                        setStreamText((current) => (current || "") + data.text);
                    } else if (name === "done") {
                        const message = data.assistant_message;
                        setMessages((current) => [...current, message]);
                        setSourcesByMessage((current) => ({
                            ...current,
                            [message.id]: message.sources?.length ? message.sources : data.sources || [],
                        }));
                        setStreamText(null);
                    } else if (name === "error") {
                        throw new Error(data.detail);
                    }
                });
            } catch (streamError) {
                // Older backends have no streaming endpoint: ask the normal way.
                if (started || ![404, 405].includes(streamError.status)) {
                    throw streamError;
                }

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
            setStreamText(null);
            setBusy("");
            inputRef.current?.focus();
        }
    };

    // ============================================================
    // QUESTION SENT FROM ANOTHER PAGE
    // ============================================================
    // e.g. "Ask" next to a key point on the document page.
    useEffect(() => {
        if (loading || !pendingPrompt || handledPromptRef.current) {
            return;
        }

        handledPromptRef.current = true;
        onPromptConsumed();
        send(pendingPrompt.text);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [loading]);

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
            writeJSON(sourcesKey(userId, chatId), null);
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
    // READ ANSWER ALOUD
    // ============================================================
    const toggleSpeak = (message) => {
        if (speakingId === message.id) {
            stopSpeaking();
            setSpeakingId(null);
            return;
        }

        setSpeakingId(message.id);
        speak(stripMarkdown(message.content), {
            onEnd: () => setSpeakingId((current) => (current === message.id ? null : current)),
        });
    };

    // ============================================================
    // VOICE INPUT
    // ============================================================
    // Dictated words are added after anything already typed.
    const toggleDictation = () => {
        if (listening) {
            stopDictationRef.current?.();
            return;
        }

        const typed = question.trim();
        setError("");
        setListening(true);

        stopDictationRef.current = startDictation({
            onText: (spoken) => {
                setQuestion(typed ? `${typed} ${spoken}` : spoken);
                requestAnimationFrame(resizeInput);
            },
            onEnd: () => {
                setListening(false);
                stopDictationRef.current = null;
                inputRef.current?.focus();
            },
            onError: setError,
        });
    };

    // ============================================================
    // EXPORT (MARKDOWN AND PRINT / PDF)
    // ============================================================
    const exportMarkdown = () => {
        const scopeLabel = chat?.document_id
            ? documentNames[chat.document_id] || "Linked document"
            : "All documents";

        downloadTextFile(
            safeFilename(chat?.title, "md"),
            chatToMarkdown({ title: chat?.title, scopeLabel, messages, sourcesByMessage, documentNames })
        );
    };

    // ============================================================
    // RENDER
    // ============================================================
    const currentScope = chatId ? chat?.document_id || "" : scope;
    const scopeOptions = [
        ...(chatId && chat?.document_id ? [] : [{ value: "", label: "All documents" }]),
        ...readyDocuments.map((doc) => ({ value: doc.id, label: doc.filename })),
    ];

    // A chat about one summarised document suggests questions from its key points.
    const scopeDocument = readyDocuments.find((doc) => doc.id === currentScope);
    const documentSuggestions = keyPointQuestions(scopeDocument?.key_points).map((item) => ({
        ...item,
        icon: "sparkles",
    }));
    const welcomeSuggestions = documentSuggestions.length > 0 ? documentSuggestions : suggestions;

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
                                disabled={!hasReadyDocuments || readOnly}
                            />
                            {chat?.document_id && documentNames[chat.document_id] && (
                                <button className="link-button" onClick={() => onOpenDocument(chat.document_id)}>
                                    Open
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {chatId && !renaming && (
                    <div className="cb-header-actions">
                        {readOnly && <span className="shared-tag">Shared by {chat?.owner_name || "another user"}</span>}
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
                                {messages.length > 0 && (
                                    <>
                                        <button
                                            className="cb-icon-button"
                                            title="Download chat (Markdown)"
                                            onClick={exportMarkdown}
                                        >
                                            <Icon name="download" size={15} />
                                        </button>
                                        <button
                                            className="cb-icon-button"
                                            title="Print or save as PDF"
                                            onClick={() => window.print()}
                                        >
                                            <Icon name="printer" size={15} />
                                        </button>
                                    </>
                                )}
                                {!readOnly && (
                                    <>
                                        <button
                                            className="cb-icon-button"
                                            title="Share chat (read-only)"
                                            onClick={() => setShowShare(true)}
                                        >
                                            <Icon name="share" size={15} />
                                        </button>
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

                        {hasReadyDocuments && documentSuggestions.length > 0 && (
                            <div className="cb-suggestions-label">
                                Suggested from the key points of {scopeDocument.filename}
                            </div>
                        )}

                        {hasReadyDocuments ? (
                            <div className="cb-suggestions">
                                {welcomeSuggestions.map((item) => (
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
                        {messages.map((message, index) =>
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
                                                            highlight={
                                                                messages
                                                                    .slice(0, index)
                                                                    .findLast((item) => item.role === "user")?.content
                                                            }
                                                            compact
                                                        />
                                                    </details>
                                                )}
                                                <div className="cb-answer-actions">
                                                    <button onClick={() => copy(message)} title="Copy answer">
                                                        <Icon name={copiedId === message.id ? "checkMark" : "copy"} size={13} />
                                                        {copiedId === message.id ? "Copied" : "Copy"}
                                                    </button>
                                                    {readAloudSupported && (
                                                        <button
                                                            onClick={() => toggleSpeak(message)}
                                                            title={speakingId === message.id ? "Stop reading" : "Read aloud"}
                                                        >
                                                            <Icon name={speakingId === message.id ? "stop" : "volume"} size={13} />
                                                            {speakingId === message.id ? "Stop" : "Listen"}
                                                        </button>
                                                    )}
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

                        {streamText !== null && (
                            <div className="cb-row cb-row-assistant">
                                <span className="cb-avatar">
                                    <Icon name="sparkles" size={24} gradient strokeWidth={1.7} />
                                </span>
                                <div className="cb-answer">
                                    <div className="cb-answer-name">DocuMind AI</div>
                                    {streamText ? (
                                        <Markdown text={streamText} />
                                    ) : (
                                        <div className="cb-typing" aria-label="DocuMind AI is thinking">
                                            <span />
                                            <span />
                                            <span />
                                        </div>
                                    )}
                                </div>
                            </div>
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

                {readOnly ? (
                    <div className="cb-readonly">
                        <Icon name="lock" size={14} /> This chat was shared with you to read. Start your own chat to ask
                        questions.
                    </div>
                ) : (
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
                        data-shortcut-focus
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
                            listening
                                ? "Listening..."
                                : hasReadyDocuments
                                    ? "Message DocuMind AI..."
                                    : "Upload a document to start chatting"
                        }
                        maxLength={5000}
                        disabled={!hasReadyDocuments || busy === "ask"}
                    />
                    {voiceInputSupported && (
                        <button
                            type="button"
                            className={`cb-icon-button ${listening ? "is-listening" : ""}`}
                            onClick={toggleDictation}
                            disabled={!hasReadyDocuments || busy === "ask"}
                            title={listening ? "Stop voice input" : "Voice input"}
                            aria-pressed={listening}
                        >
                            <Icon name="mic" size={17} />
                        </button>
                    )}
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
                )}
                <div className="cb-hint">
                    Answers come from your documents. <kbd>Enter</kbd> to send · <kbd>Shift</kbd> +{" "}
                    <kbd>Enter</kbd> for a new line
                </div>
            </div>

            {showShare && (
                <ShareDialog
                    title={`Share "${chat?.title || "chat"}"`}
                    subtitle="People you share with can read this conversation. They cannot add to it."
                    roles={["viewer"]}
                    loadShares={() => listChatShares(chatId)}
                    addShare={(share) => shareChat(chatId, share)}
                    removeShare={(shareUserId) => removeChatShare(chatId, shareUserId)}
                    onClose={() => setShowShare(false)}
                />
            )}
        </section>
    );
}

// ============================================================
// CHAT PAGE: HISTORY SIDEBAR + CONVERSATION
// ============================================================

function ChatView({
    userId,
    pendingPrompt,
    onPromptConsumed,
    chats,
    sharedChats = [],
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

    // Shared chats open read-only under a "shared-" key.
    const openSharedChat = (chatId) => {
        setConversationKey(`shared-${chatId}`);
        setHistoryOpen(false);
    };

    const visibleShared = sharedChats.filter((chat) =>
        (chat.title || "").toLowerCase().includes(filter.trim().toLowerCase())
    );
    const sharedId = conversationKey.startsWith("shared-") ? conversationKey.slice(7) : null;

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

                    {visibleShared.length > 0 && (
                        <div className="cb-history-group">
                            <div className="cb-history-label">Shared with you</div>
                            {visibleShared.map((chat) => (
                                <button
                                    key={chat.id}
                                    className={`cb-history-item ${chat.id === sharedId ? "active" : ""}`}
                                    onClick={() => openSharedChat(chat.id)}
                                >
                                    <Icon name="share" size={14} />
                                    <span>
                                        <strong>{chat.title}</strong>
                                        <small>From {chat.owner_name || "another user"} · read-only</small>
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}

                    {visibleChats.length === 0 && visibleShared.length === 0 && (
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
                initialChatId={
                    conversationKey.startsWith("new-") ? null : sharedId || conversationKey
                }
                sharedChat={sharedId ? sharedChats.find((chat) => chat.id === sharedId) || { id: sharedId } : null}
                userId={userId}
                pendingPrompt={pendingPrompt?.chatId === conversationKey ? pendingPrompt : null}
                onPromptConsumed={onPromptConsumed}
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
