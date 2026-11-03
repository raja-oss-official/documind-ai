// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import Markdown from "./Markdown.jsx";
import {
    addYouTubeVideo,
    askInChatStream,
    createChat,
    deleteDocument,
    formatTimestamp,
    getChatMessages,
    parseTimestamp,
} from "../api.js";

// ============================================================
// QUICK QUESTIONS
// ============================================================
const quickQuestions = [
    "What is this video about?",
    "List the key points.",
    "What tools or examples are shown?",
    "What is the main conclusion?",
];

// ============================================================
// SOURCE TIMESTAMPS
// ============================================================
// Each transcript passage starts with its time, e.g. "[01:05] ...".
function sourceTimes(sources = []) {
    const times = sources.map((source) => parseTimestamp(source.text)).filter((value) => value !== null);
    return [...new Set(times)].sort((a, b) => a - b).slice(0, 6);
}

// ============================================================
// VIDEO CHAT (ONE CONVERSATION PER VIDEO)
// ============================================================
function VideoChat({ video, chats, onChatsChanged, onSeek }) {
    // ============================================================
    // STATE
    // ============================================================
    // The most recent chat linked to this video is reused.
    const existingChat = chats.find((chat) => chat.document_id === video.id);
    const [chatId, setChatId] = useState(existingChat?.id || null);
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(Boolean(existingChat));
    const [question, setQuestion] = useState("");
    const [pending, setPending] = useState("");
    const [streamText, setStreamText] = useState(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const scrollRef = useRef(null);

    // ============================================================
    // LOAD THE CONVERSATION
    // ============================================================
    useEffect(() => {
        if (!chatId) {
            return;
        }

        let cancelled = false;

        getChatMessages(chatId)
            .then((data) => !cancelled && setMessages(Array.isArray(data) ? data : []))
            .catch((err) => !cancelled && setError(err.message))
            .finally(() => !cancelled && setLoading(false));

        return () => {
            cancelled = true;
        };
        // Only the first load; new messages are added as they arrive.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        const element = scrollRef.current;

        if (element) {
            element.scrollTo({ top: element.scrollHeight });
        }
    }, [messages, pending, streamText]);

    // ============================================================
    // ASK A QUESTION
    // ============================================================
    const ask = async (rawText) => {
        const text = (rawText ?? question).trim();

        if (!text || busy) {
            return;
        }

        setBusy(true);
        setError("");
        setPending(text);
        setQuestion("");

        try {
            let id = chatId;

            if (!id) {
                const chat = await createChat({ title: video.filename.slice(0, 200), documentId: video.id });
                id = chat.id;
                setChatId(id);
            }

            await askInChatStream(id, text, (name, data) => {
                if (name === "start") {
                    setPending("");
                    setMessages((current) => [...current, data.user_message]);
                    setStreamText("");
                } else if (name === "token") {
                    setStreamText((current) => (current || "") + data.text);
                } else if (name === "done") {
                    setMessages((current) => [...current, data.assistant_message]);
                    setStreamText(null);
                } else if (name === "error") {
                    throw new Error(data.detail);
                }
            });

            onChatsChanged();
        } catch (err) {
            setError(err.message);

            if (!chatId) {
                setQuestion(text);
            }
        } finally {
            setPending("");
            setStreamText(null);
            setBusy(false);
        }
    };

    // ============================================================
    // RENDER
    // ============================================================
    const empty = !loading && messages.length === 0 && !pending;

    return (
        <div className="yt-chat">
            <div className="yt-messages" ref={scrollRef}>
                {loading && (
                    <p className="muted">
                        <span className="spinner" /> Loading conversation...
                    </p>
                )}

                {empty && (
                    <div className="yt-empty">
                        <strong>Ask anything about this video</strong>
                        <span>Short, clear answers with timestamps that jump to the moment in the video.</span>
                        <div className="yt-quick">
                            {quickQuestions.map((item) => (
                                <button key={item} onClick={() => ask(item)} disabled={busy}>
                                    {item}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((message) =>
                    message.role === "assistant" ? (
                        <div className="yt-answer" key={message.id}>
                            <Icon name="sparkles" size={18} gradient strokeWidth={1.7} />
                            <div>
                                <Markdown text={message.content} onTimestamp={onSeek} />
                                {sourceTimes(message.sources).length > 0 && (
                                    <div className="yt-sources">
                                        <span>Sources</span>
                                        {sourceTimes(message.sources).map((seconds) => (
                                            <button key={seconds} className="yt-time" onClick={() => onSeek(seconds)}>
                                                {formatTimestamp(seconds)}
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <div className="yt-question" key={message.id}>
                            {message.content}
                        </div>
                    )
                )}

                {pending && <div className="yt-question">{pending}</div>}

                {(pending || streamText !== null) && (
                    <div className="yt-answer">
                        <Icon name="sparkles" size={18} gradient strokeWidth={1.7} />
                        <div>
                            {streamText ? (
                                <Markdown text={streamText} onTimestamp={onSeek} />
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
            </div>

            {error && (
                <div className="notice notice-error" role="alert">
                    <span>{error}</span>
                    <button className="notice-close" onClick={() => setError("")}>
                        <Icon name="close" size={14} />
                    </button>
                </div>
            )}

            <form
                className="yt-composer"
                onSubmit={(event) => {
                    event.preventDefault();
                    ask();
                }}
            >
                <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="Ask about this video..."
                    maxLength={2000}
                    data-shortcut-focus
                    disabled={busy}
                />
                <button className="cb-send" type="submit" disabled={!question.trim() || busy} title="Ask">
                    {busy ? <span className="spinner spinner-light" /> : <Icon name="arrowUp" size={18} />}
                </button>
            </form>
        </div>
    );
}

// ============================================================
// YT AI CHAT PAGE
// ============================================================
function YouTubeView({ videos, chats, onVideosChanged, onChatsChanged }) {
    // ============================================================
    // STATE
    // ============================================================
    const [url, setUrl] = useState("");
    const [adding, setAdding] = useState(false);
    const [error, setError] = useState("");
    const [selectedId, setSelectedId] = useState(null);
    const [confirmDelete, setConfirmDelete] = useState(null);
    const [seek, setSeek] = useState({ start: 0, nonce: 0 });

    // Default to the newest ready video.
    const selected =
        videos.find((video) => video.id === selectedId) ||
        videos.find((video) => video.status === "completed") ||
        videos[0];

    // ============================================================
    // ADD AND DELETE VIDEOS
    // ============================================================
    const handleAdd = async (event) => {
        event.preventDefault();
        setAdding(true);
        setError("");

        try {
            const result = await addYouTubeVideo(url.trim());
            setUrl("");
            setSelectedId(result.id);
            setSeek({ start: 0, nonce: Date.now() });
            await onVideosChanged();
        } catch (err) {
            setError(err.message);
        } finally {
            setAdding(false);
        }
    };

    const handleDelete = async (videoId) => {
        try {
            await deleteDocument(videoId);
            setConfirmDelete(null);

            if (videoId === selected?.id) {
                setSelectedId(null);
            }

            await onVideosChanged();
        } catch (err) {
            setError(err.message);
        }
    };

    const seekTo = (seconds) => setSeek({ start: seconds, nonce: Date.now() });

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="yt-layout">
            {/* ============================================================
                VIDEOS
                ============================================================ */}
            <aside className="panel yt-sidebar">
                <form className="yt-add" onSubmit={handleAdd}>
                    <label htmlFor="yt-url">Add a YouTube video</label>
                    <div className="yt-add-row">
                        <input
                            id="yt-url"
                            className="text-input"
                            value={url}
                            onChange={(event) => setUrl(event.target.value)}
                            placeholder="https://www.youtube.com/watch?v=…"
                            required
                        />
                        <button className="button button-primary" type="submit" disabled={adding || !url.trim()}>
                            {adding ? <span className="spinner spinner-light" /> : <Icon name="plus" />}
                            {adding ? "Adding..." : "Add"}
                        </button>
                    </div>
                    <span className="muted">Public videos only. Gemini watches the whole video, which can take a minute.</span>
                </form>

                {error && (
                    <div className="notice notice-error" role="alert">
                        {error}
                    </div>
                )}

                <div className="yt-list">
                    {videos.length === 0 && (
                        <div className="empty-state">
                            <div className="empty-icon">
                                <Icon name="youtube" size={22} />
                            </div>
                            <strong>No videos yet</strong>
                            <span>Paste a YouTube link above to start.</span>
                        </div>
                    )}

                    {videos.map((video) => (
                        <div key={video.id} className={`yt-item ${video.id === selected?.id ? "active" : ""}`}>
                            <button className="yt-item-main" onClick={() => setSelectedId(video.id)}>
                                <img src={`https://i.ytimg.com/vi/${video.video_id}/mqdefault.jpg`} alt="" loading="lazy" />
                                <span className="yt-item-text">
                                    <strong>{video.filename}</strong>
                                    <small>
                                        {video.status === "processing" && (
                                            <>
                                                <span className="spinner" /> Watching the video...
                                            </>
                                        )}
                                        {video.status === "failed" && <span className="yt-failed">Could not read this video</span>}
                                        {video.status === "completed" &&
                                            [video.author, video.duration_seconds ? formatTimestamp(video.duration_seconds) : ""]
                                                .filter(Boolean)
                                                .join(" · ")}
                                    </small>
                                </span>
                            </button>
                            {confirmDelete === video.id ? (
                                <span className="yt-confirm">
                                    <button className="button button-danger button-small" onClick={() => handleDelete(video.id)}>
                                        Delete
                                    </button>
                                    <button className="button button-small" onClick={() => setConfirmDelete(null)}>
                                        Cancel
                                    </button>
                                </span>
                            ) : (
                                <button
                                    className="cb-icon-button cb-icon-danger"
                                    onClick={() => setConfirmDelete(video.id)}
                                    title="Delete video"
                                    aria-label={`Delete ${video.filename}`}
                                >
                                    <Icon name="trash" size={14} />
                                </button>
                            )}
                        </div>
                    ))}
                </div>
            </aside>

            {/* ============================================================
                PLAYER AND CHAT
                ============================================================ */}
            <section className="panel yt-main">
                {!selected ? (
                    <div className="empty-state yt-placeholder">
                        <div className="empty-icon">
                            <Icon name="youtube" size={26} />
                        </div>
                        <strong>Chat with any YouTube video</strong>
                        <span>Add a link, then ask questions. Answers are short and clear, with timestamps that jump to the right moment.</span>
                    </div>
                ) : (
                    <>
                        <div className="yt-player">
                            <iframe
                                key={`${selected.id}-${seek.nonce}`}
                                src={`https://www.youtube-nocookie.com/embed/${selected.video_id}?rel=0${
                                    seek.nonce && seek.start >= 0 ? `&start=${seek.start}&autoplay=1` : ""
                                }`}
                                title={selected.filename}
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                allowFullScreen
                            />
                        </div>

                        <div className="yt-title">
                            <h2>{selected.filename}</h2>
                            {selected.source_url && (
                                <a className="link-button" href={selected.source_url} target="_blank" rel="noreferrer">
                                    Open on YouTube <Icon name="arrowRight" size={13} />
                                </a>
                            )}
                        </div>

                        {selected.status === "completed" && (
                            <VideoChat
                                key={selected.id}
                                video={selected}
                                chats={chats}
                                onChatsChanged={onChatsChanged}
                                onSeek={seekTo}
                            />
                        )}

                        {selected.status === "processing" && (
                            <p className="muted yt-status">
                                <span className="spinner" /> Gemini is watching the video and writing a timestamped
                                transcript. Chat opens when it's ready.
                            </p>
                        )}

                        {selected.status === "failed" && (
                            <div className="notice notice-error">
                                {selected.processing_error || "This video could not be processed."} Delete it and try
                                again, or try a shorter public video.
                            </div>
                        )}
                    </>
                )}
            </section>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default YouTubeView;
