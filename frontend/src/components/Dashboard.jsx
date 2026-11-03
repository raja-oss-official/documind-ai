// ============================================================
// IMPORTS
// ============================================================
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import "../styles/Dashboard.css";
import "../styles/DarkTheme.css";
import logoLight from "../assets/documind-logo-light.png";
import logoDark from "../assets/documind-logo-dark.png";
import {
    MAX_UPLOAD_SIZE,
    SUPPORTED_EXTENSIONS,
    checkHealth,
    createChat,
    fileExtension,
    isVideo,
    listChats,
    listDocuments,
    listSharedChats,
    uploadDocument,
    waitForDocument,
} from "../api.js";
import Overview from "./Overview.jsx";
import DocumentTable from "./DocumentTable.jsx";
import DocumentDetails from "./DocumentDetails.jsx";
import SearchView from "./SearchView.jsx";
import ChatView from "./ChatView.jsx";
import AccountView from "./AccountView.jsx";
import YouTubeView from "./YouTubeView.jsx";
import Credits from "./Credits.jsx";
import ShortcutsDialog from "./ShortcutsDialog.jsx";
import { THEME_KEY, readJSON, writeJSON } from "../storage.js";

// ============================================================
// NAVIGATION AND PAGE TEXT
// ============================================================
const navItems = [
    { label: "Dashboard", icon: "dashboard" },
    { label: "Documents", icon: "documents" },
    { label: "AI Search", icon: "search" },
    { label: "AI Chat", icon: "chat" },
    { label: "YT AI Chat", icon: "youtube" },
    { label: "Account", icon: "user" },
];

const pageDescriptions = {
    Dashboard: "Upload documents, find information, and get answers with AI.",
    Documents: "Manage your documents in one place.",
    "AI Search": "Search across your documents to find relevant information.",
    "AI Chat": "Ask questions about your documents in natural language.",
    "YT AI Chat": "Paste a YouTube link and get brief answers about the video.",
    Account: "Manage your profile and account security.",
};

const uploadStatusLabels = {
    waiting: "Waiting",
    uploading: "Processing...",
    done: "Ready",
    failed: "Failed",
};

const apiStatusLabels = {
    checking: "Checking API connection...",
    online: "API connected",
    offline: "API unavailable",
};

// ============================================================
// WORKSPACE SHELL (SIDEBAR, TOP BAR, PAGES)
// ============================================================
function Dashboard({ user, onLogout }) {
    // ============================================================
    // STATE
    // ============================================================
    const [activePage, setActivePage] = useState("Dashboard");
    const [pendingSearch, setPendingSearch] = useState(null);
    const [apiStatus, setApiStatus] = useState("checking");

    const [documents, setDocuments] = useState([]);
    const [documentsLoading, setDocumentsLoading] = useState(true);
    const [documentsError, setDocumentsError] = useState("");
    const [selectedDocumentId, setSelectedDocumentId] = useState(null);
    const [documentFilter, setDocumentFilter] = useState("");
    const [statusFilter, setStatusFilter] = useState("all");

    const [chats, setChats] = useState([]);
    const [sharedChats, setSharedChats] = useState([]);
    const [activeChatId, setActiveChatId] = useState(null);

    const [uploadState, setUploadState] = useState({ active: false, fileName: "", index: 0, total: 0 });
    const [uploadItems, setUploadItems] = useState([]);
    const [notice, setNotice] = useState(null);
    const [pendingPrompt, setPendingPrompt] = useState(null);
    const [chatViewKey, setChatViewKey] = useState(0);
    const [showShortcuts, setShowShortcuts] = useState(false);
    const [theme, setTheme] = useState(
        () =>
            readJSON(THEME_KEY, null) ||
            (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    );
    const [dragging, setDragging] = useState(false);
    const fileInputRef = useRef(null);
    const dragDepth = useRef(0);

    // ============================================================
    // DATA LOADING
    // ============================================================

    const refreshDocuments = useCallback(
        () =>
            listDocuments()
                .then((data) => {
                    setDocuments(Array.isArray(data) ? data : []);
                    setDocumentsError("");
                })
                .catch((error) => setDocumentsError(error.message))
                .finally(() => setDocumentsLoading(false)),
        []
    );

    const refreshChats = useCallback(
        () =>
            Promise.all([
                listChats()
                    .then((data) => setChats(Array.isArray(data) ? data : []))
                    .catch((error) => setNotice({ type: "error", text: error.message })),
                // Chats other users shared (read-only); empty on older backends.
                listSharedChats()
                    .then((data) => setSharedChats(Array.isArray(data) ? data : []))
                    .catch(() => setSharedChats([])),
            ]),
        []
    );

    useEffect(() => {
        checkHealth()
            .then(() => setApiStatus("online"))
            .catch(() => setApiStatus("offline"));

        refreshDocuments();
        refreshChats();
    }, [refreshDocuments, refreshChats]);

    // ============================================================
    // BACKGROUND PROCESSING STATUS
    // ============================================================
    // Uploads are processed on the server after the request returns;
    // refresh the list until no document is still processing.
    const anyProcessing = documents.some((doc) => doc.status === "processing");

    useEffect(() => {
        if (!anyProcessing) {
            return;
        }

        const timer = setInterval(refreshDocuments, 4000);
        return () => clearInterval(timer);
    }, [anyProcessing, refreshDocuments]);

    // ============================================================
    // THEME (LIGHT / DARK)
    // ============================================================
    // Applied to <html> so the theme variables reach every element.
    // A layout effect sets it before the first paint (no light flash).
    // The sign-in page always stays light.
    useLayoutEffect(() => {
        const root = document.documentElement;
        root.dataset.theme = theme;

        // Printing (chat export as PDF) always uses the light theme.
        const printLight = () => {
            root.dataset.theme = "light";
        };
        const restore = () => {
            root.dataset.theme = theme;
        };

        window.addEventListener("beforeprint", printLight);
        window.addEventListener("afterprint", restore);

        return () => {
            window.removeEventListener("beforeprint", printLight);
            window.removeEventListener("afterprint", restore);
            delete root.dataset.theme;
        };
    }, [theme]);

    const toggleTheme = () => {
        const next = theme === "dark" ? "light" : "dark";
        setTheme(next);
        writeJSON(THEME_KEY, next);
    };

    // ============================================================
    // UPLOAD
    // ============================================================

    const uploadFiles = async (files) => {
        if (files.length === 0 || uploadState.active) {
            return;
        }

        setNotice(null);

        const problems = [];
        let uploadedCount = 0;

        // Every file gets a row in the progress card when several are uploaded.
        const markItem = (index, status, message = "") =>
            setUploadItems((items) =>
                items.map((item, itemIndex) => (itemIndex === index ? { ...item, status, message } : item))
            );

        setUploadItems(files.map((file) => ({ name: file.name, status: "waiting", message: "" })));

        for (const [index, file] of files.entries()) {
            const extension = fileExtension(file.name);

            if (!SUPPORTED_EXTENSIONS.includes(extension)) {
                problems.push(`${file.name}: unsupported file type`);
                markItem(index, "failed", "Unsupported file type");
                continue;
            }

            if (file.size > MAX_UPLOAD_SIZE) {
                problems.push(`${file.name}: exceeds the 10 MB limit`);
                markItem(index, "failed", "Larger than 10 MB");
                continue;
            }

            setUploadState({ active: true, fileName: file.name, index: index + 1, total: files.length });
            markItem(index, "uploading");

            try {
                let result = await uploadDocument(file);
                await refreshDocuments();

                // The server processes the file in the background.
                if (result.status === "processing") {
                    const processed = await waitForDocument(result.id);
                    result = { ...processed, message: processed.processing_error };
                }

                if (result.status === "failed") {
                    problems.push(`${file.name}: ${result.message || "processing failed"}`);
                    markItem(index, "failed", result.message || "Processing failed");
                } else {
                    uploadedCount += 1;
                    markItem(index, "done");
                }
            } catch (error) {
                problems.push(`${file.name}: ${error.message}`);
                markItem(index, "failed", error.message);
            }

            await refreshDocuments();
        }

        setUploadState({ active: false, fileName: "", index: 0, total: 0 });
        setUploadItems([]);

        if (problems.length > 0) {
            setNotice({
                type: "error",
                text: `${uploadedCount} of ${files.length} uploaded. ${problems.join(" · ")}`,
            });
        } else {
            setNotice({
                type: "success",
                text: `${uploadedCount} ${uploadedCount === 1 ? "document" : "documents"} uploaded and processed.`,
            });
        }
    };

    const handleFileInput = (event) => {
        const files = Array.from(event.target.files || []);
        event.target.value = "";
        uploadFiles(files);
    };

    // ============================================================
    // DRAG AND DROP UPLOAD
    // ============================================================
    // Drag files anywhere over the workspace to upload them.
    const dragHandlers = {
        onDragEnter: (event) => {
            if (!event.dataTransfer?.types?.includes("Files")) {
                return;
            }

            event.preventDefault();
            dragDepth.current += 1;
            setDragging(true);
        },
        onDragOver: (event) => {
            if (event.dataTransfer?.types?.includes("Files")) {
                event.preventDefault();
            }
        },
        onDragLeave: () => {
            dragDepth.current = Math.max(0, dragDepth.current - 1);

            if (dragDepth.current === 0) {
                setDragging(false);
            }
        },
        onDrop: (event) => {
            event.preventDefault();
            dragDepth.current = 0;
            setDragging(false);
            uploadFiles(Array.from(event.dataTransfer?.files || []));
        },
    };

    // ============================================================
    // NAVIGATION HELPERS
    // ============================================================

    const navigate = (page) => {
        setActivePage(page);
        setNotice(null);

        if (page !== "Documents") {
            setSelectedDocumentId(null);
        }
    };

    const openDocument = (documentId) => {
        // YouTube videos live on their own page.
        if (isVideo(documents.find((doc) => doc.id === documentId))) {
            navigate("YT AI Chat");
            return;
        }

        setSelectedDocumentId(documentId);
        setActivePage("Documents");
        setNotice(null);
    };

    const openChat = (chatId) => {
        setActiveChatId(chatId);
        navigate("AI Chat");
    };

    const startNewChat = async () => {
        try {
            const chat = await createChat({ title: "New Chat" });
            await refreshChats();
            openChat(chat.id);
        } catch (error) {
            setNotice({ type: "error", text: error.message });
        }
    };

    const startSearch = (query, documentId = "") => {
        setPendingSearch({ query, documentId, id: Date.now() });
        navigate("AI Search");
    };

    // Opens an empty conversation; the chat is created on the first message.
    const openBlankChat = () => {
        setActiveChatId(null);
        setChatViewKey((key) => key + 1);
        navigate("AI Chat");
    };

    // "Ask" next to a key point: a chat linked to the document, question sent on open.
    const askAboutDocument = async (document, { title, prompt }) => {
        try {
            const chat = await createChat({ title, documentId: document.id });
            await refreshChats();
            setPendingPrompt({ chatId: chat.id, text: prompt });
            openChat(chat.id);
        } catch (error) {
            setNotice({ type: "error", text: error.message });
        }
    };

    // ============================================================
    // KEYBOARD SHORTCUTS
    // ============================================================
    // The listener is registered once and always calls the latest handler.
    const shortcutHandler = useRef(null);

    useEffect(() => {
        shortcutHandler.current = (event) => {
            const key = event.key;
            const typing = event.target.closest?.("input, textarea, select, [contenteditable='true']");

            if ((event.metaKey || event.ctrlKey) && key.toLowerCase() === "k") {
                event.preventDefault();

                if (activePage === "AI Search") {
                    document.querySelector("[data-shortcut-focus]")?.focus();
                } else {
                    navigate("AI Search");
                }
                return;
            }

            if (typing || event.metaKey || event.ctrlKey || event.altKey || document.querySelector(".modal-backdrop")) {
                return;
            }

            const pageIndex = Number(key) - 1;
            const lower = key.toLowerCase();
            const handled = key === "/" || key === "?" || Boolean(navItems[pageIndex]) || ["n", "u", "t"].includes(lower);

            if (!handled) {
                return;
            }

            // The page that opens may focus a text box; keep the key out of it.
            event.preventDefault();

            if (key === "/") {
                const field = document.querySelector("[data-shortcut-focus]");

                if (field) {
                    field.focus();
                } else {
                    navigate("AI Search");
                }
            } else if (navItems[pageIndex]) {
                navigate(navItems[pageIndex].label);
            } else if (lower === "n") {
                openBlankChat();
            } else if (lower === "u" && !uploadState.active) {
                fileInputRef.current?.click();
            } else if (lower === "t") {
                toggleTheme();
            } else if (key === "?") {
                setShowShortcuts(true);
            }
        };
    });

    useEffect(() => {
        const handleKey = (event) => shortcutHandler.current(event);
        document.addEventListener("keydown", handleKey);
        return () => document.removeEventListener("keydown", handleKey);
    }, []);

    // ============================================================
    // DERIVED VALUES
    // ============================================================
    const completedDocuments = documents.filter((doc) => doc.status === "completed");
    const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId);
    const fileDocuments = documents.filter((doc) => !isVideo(doc));
    const videos = documents.filter(isVideo);
    const filteredDocuments = fileDocuments.filter(
        (doc) =>
            (statusFilter === "all" || doc.status === statusFilter) &&
            (doc.filename || "").toLowerCase().includes(documentFilter.toLowerCase())
    );
    const displayName = user?.name || "Your workspace";
    const isChat = activePage === "AI Chat";

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="app-shell">
            {/* ============================================================
                SIDEBAR
                ============================================================ */}
            <aside className="sidebar">
                <div className="brand">
                    <div className="logo-lockup">
                        <img className="brand-logo" src={theme === "dark" ? logoDark : logoLight} alt="DocuMind AI" />
                        <span className="logo-slogan">Document Intelligence</span>
                    </div>
                </div>

                <div className="nav-heading">WORKSPACE</div>
                {/* ============================================================
                    NAVIGATION
                    ============================================================ */}
                <nav className="navigation">
                    {navItems.map((item) => (
                        <button
                            key={item.label}
                            className={`nav-item ${activePage === item.label ? "active" : ""}`}
                            onClick={() => navigate(item.label)}
                        >
                            <Icon name={item.icon} size={18} className="nav-icon" />
                            <span>{item.label}</span>
                        </button>
                    ))}
                </nav>

                {/* ============================================================
                    PROFILE AND SIGN OUT
                    ============================================================ */}
                <div className="sidebar-bottom">
                    <div className="status-indicator">
                        <span className="status-dot" />
                        {completedDocuments.length}{" "}
                        {completedDocuments.length === 1 ? "document" : "documents"} ready
                    </div>
                    <div className="profile">
                        <div className="avatar">{displayName.charAt(0).toUpperCase()}</div>
                        <div className="profile-text">
                            <div className="profile-name">{displayName}</div>
                            <div className="profile-caption">{user?.email}</div>
                        </div>
                    </div>
                    <button className="button sign-out-button" onClick={() => onLogout()}>
                        <Icon name="logout" /> Sign out
                    </button>
                </div>
            </aside>

            {/* ============================================================
                MAIN CONTENT
                ============================================================ */}
            <main className="main-content" {...dragHandlers}>
                {/* ============================================================
                    DROP OVERLAY
                    ============================================================ */}
                {dragging && (
                    <div className="drop-overlay">
                        <div className="drop-overlay-card">
                            <Icon name="upload" size={28} />
                            <strong>Drop files to upload</strong>
                            <span>PDF, DOCX, TXT, CSV, XLSX, PPTX, PNG, JPG · up to 10 MB each</span>
                        </div>
                    </div>
                )}

                {/* ============================================================
                    TOP BAR
                    ============================================================ */}
                <header className="topbar">
                    <div className="breadcrumb">
                        Workspace <span>/</span> <strong>{activePage}</strong>
                    </div>
                    <div className="topbar-actions">
                        <div className={`api-status api-status-${apiStatus}`}>
                            <span className="status-dot" />
                            {apiStatusLabels[apiStatus]}
                        </div>
                        <button
                            className="cb-icon-button topbar-button topbar-shortcuts"
                            onClick={() => setShowShortcuts(true)}
                            title="Keyboard shortcuts (?)"
                        >
                            <Icon name="keyboard" size={16} />
                        </button>
                        <button
                            className="cb-icon-button topbar-button"
                            onClick={toggleTheme}
                            title={theme === "dark" ? "Switch to light theme (T)" : "Switch to dark theme (T)"}
                            aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
                        >
                            <Icon name={theme === "dark" ? "sun" : "moon"} size={16} />
                        </button>
                    </div>
                </header>

                <section className={`page-content ${isChat ? "page-content-chat" : ""}`}>
                    {/* ============================================================
                        HIDDEN FILE INPUT
                        ============================================================ */}
                    <input
                        ref={fileInputRef}
                        className="hidden-input"
                        type="file"
                        accept={SUPPORTED_EXTENSIONS.join(",")}
                        multiple
                        onChange={handleFileInput}
                    />

                    {/* ============================================================
                        PAGE HEADING
                        ============================================================ */}
                    {!isChat && (
                    <div className="page-heading">
                        <div>
                            <div className="eyebrow">DOCUMENT INTELLIGENCE</div>
                            <h1>
                                {activePage === "Dashboard"
                                    ? `Welcome back, ${displayName.split(" ")[0]}.`
                                    : activePage}
                            </h1>
                            <p className="page-description">{pageDescriptions[activePage]}</p>
                        </div>
                        {activePage === "Documents" && (
                            <button
                                className="button button-primary upload-button"
                                onClick={() => fileInputRef.current?.click()}
                                disabled={uploadState.active}
                            >
                                <Icon name="upload" /> {uploadState.active ? "Uploading..." : "Upload documents"}
                            </button>
                        )}
                    </div>
                    )}

                    {/* ============================================================
                        UPLOAD PROGRESS
                        ============================================================ */}
                    {uploadState.active && (
                        <div className="upload-progress" role="status">
                            <div className="upload-progress-icon">
                                <Icon name="upload" size={18} />
                            </div>
                            <div className="upload-progress-body">
                                <div className="upload-progress-title">
                                    <strong>Uploading and processing</strong>
                                    {uploadState.total > 1 && (
                                        <span>
                                            {uploadState.index} of {uploadState.total}
                                        </span>
                                    )}
                                </div>
                                <div className="upload-progress-file">{uploadState.fileName}</div>
                                <div className="loading-bar upload-progress-bar" aria-hidden="true">
                                    <span />
                                </div>
                                <div className="upload-progress-steps">
                                    Extracting text, indexing for AI search. Large or scanned files can take a minute.
                                </div>
                                {uploadItems.length > 1 && (
                                    <ul className="upload-queue">
                                        {uploadItems.map((item, index) => (
                                            <li key={`${item.name}-${index}`} className={`upload-queue-${item.status}`}>
                                                <span className="upload-queue-name">{item.name}</span>
                                                <span className="upload-queue-status" title={item.message}>
                                                    {item.status === "uploading" && <span className="spinner" />}
                                                    {item.status === "done" && <Icon name="checkMark" size={13} />}
                                                    {item.status === "failed" && <Icon name="close" size={13} />}
                                                    {item.status === "failed" && item.message
                                                        ? item.message
                                                        : uploadStatusLabels[item.status]}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>
                        </div>
                    )}

                    {/* ============================================================
                        NOTICES
                        ============================================================ */}
                    {notice && (
                        <div className={`notice notice-${notice.type}`} role="status">
                            <span>{notice.text}</span>
                            <button className="notice-close" onClick={() => setNotice(null)}>
                                <Icon name="close" size={14} />
                            </button>
                        </div>
                    )}

                    {/* ============================================================
                        DASHBOARD PAGE
                        ============================================================ */}
                    {activePage === "Dashboard" && (
                        <Overview
                            documents={documents}
                            chats={chats}
                            loading={documentsLoading}
                            onUploadClick={() => fileInputRef.current?.click()}
                            onOpenDocument={openDocument}
                            onOpenChat={openChat}
                            onNewChat={startNewChat}
                            onSearch={(query) => startSearch(query)}
                            onNavigate={navigate}
                        />
                    )}

                    {/* ============================================================
                        DOCUMENTS PAGE
                        ============================================================ */}
                    {activePage === "Documents" && selectedDocument && (
                        <DocumentDetails
                            key={selectedDocument.id}
                            document={selectedDocument}
                            documents={documents}
                            userId={user?.id}
                            onBack={() => setSelectedDocumentId(null)}
                            onChanged={refreshDocuments}
                            onDeleted={(message) => {
                                setSelectedDocumentId(null);
                                setNotice({ type: "success", text: message || "Document deleted successfully." });
                                refreshDocuments();
                            }}
                            onSearch={(documentId) => startSearch("", documentId)}
                            onAsk={(question) => askAboutDocument(selectedDocument, question)}
                            onChatCreated={async (chat) => {
                                await refreshChats();
                                openChat(chat.id);
                            }}
                        />
                    )}

                    {activePage === "Documents" && !selectedDocument && (
                        <DocumentTable
                            documents={filteredDocuments}
                            allDocuments={fileDocuments}
                            loading={documentsLoading}
                            error={documentsError}
                            onRetry={refreshDocuments}
                            onOpen={openDocument}
                            onUploadClick={() => fileInputRef.current?.click()}
                            filter={documentFilter}
                            onFilterChange={setDocumentFilter}
                            statusFilter={statusFilter}
                            onStatusFilterChange={setStatusFilter}
                        />
                    )}

                    {/* ============================================================
                        AI SEARCH PAGE
                        ============================================================ */}
                    {activePage === "AI Search" && (
                        <SearchView
                            userId={user?.id}
                            documents={documents}
                            pendingSearch={pendingSearch}
                            onPendingConsumed={() => setPendingSearch(null)}
                            onOpenDocument={openDocument}
                        />
                    )}

                    {/* ============================================================
                        AI CHAT PAGE
                        ============================================================ */}
                    {activePage === "AI Chat" && (
                        <ChatView
                            key={chatViewKey}
                            userId={user?.id}
                            pendingPrompt={pendingPrompt}
                            onPromptConsumed={() => setPendingPrompt(null)}
                            chats={chats}
                            sharedChats={sharedChats}
                            documents={documents}
                            activeChatId={activeChatId}
                            onSelectChat={setActiveChatId}
                            onChatsChanged={refreshChats}
                            onOpenDocument={openDocument}
                            onUploadClick={() => fileInputRef.current?.click()}
                        />
                    )}

                    {/* ============================================================
                        YT AI CHAT PAGE
                        ============================================================ */}
                    {activePage === "YT AI Chat" && (
                        <YouTubeView
                            videos={videos}
                            chats={chats}
                            onVideosChanged={refreshDocuments}
                            onChatsChanged={refreshChats}
                        />
                    )}

                    {/* ============================================================
                        ACCOUNT PAGE
                        ============================================================ */}
                    {activePage === "Account" && (
                        <AccountView
                            user={user}
                            documentCount={documents.length}
                            chatCount={chats.length}
                            theme={theme}
                            onToggleTheme={toggleTheme}
                            onSignOut={() => onLogout()}
                            onPasswordChanged={() =>
                                onLogout("Password changed successfully. Please sign in again.")
                            }
                        />
                    )}

                    {/* ============================================================
                        PAGE FOOTER
                        ============================================================ */}
                    {!isChat && (
                    <footer className="page-footer">
                        <Credits />
                    </footer>
                    )}
                </section>
            </main>

            {/* ============================================================
                KEYBOARD SHORTCUTS DIALOG
                ============================================================ */}
            {showShortcuts && <ShortcutsDialog onClose={() => setShowShortcuts(false)} />}
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Dashboard;
