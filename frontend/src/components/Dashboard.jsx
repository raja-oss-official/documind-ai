// ============================================================
// IMPORTS
// ============================================================
import { useCallback, useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import "../styles/Dashboard.css";
import logoLight from "../assets/documind-logo-light.png";
import {
    MAX_UPLOAD_SIZE,
    SUPPORTED_EXTENSIONS,
    checkHealth,
    createChat,
    fileExtension,
    listChats,
    listDocuments,
    uploadDocument,
} from "../api.js";
import Overview from "./Overview.jsx";
import DocumentTable from "./DocumentTable.jsx";
import DocumentDetails from "./DocumentDetails.jsx";
import SearchView from "./SearchView.jsx";
import ChatView from "./ChatView.jsx";
import AccountView from "./AccountView.jsx";
import Credits from "./Credits.jsx";

// ============================================================
// NAVIGATION AND PAGE TEXT
// ============================================================
const navItems = [
    { label: "Dashboard", icon: "dashboard" },
    { label: "Documents", icon: "documents" },
    { label: "AI Search", icon: "search" },
    { label: "AI Chat", icon: "chat" },
    { label: "Account", icon: "user" },
];

const pageDescriptions = {
    Dashboard: "Upload documents, find information, and get answers with AI.",
    Documents: "Manage your documents in one place.",
    "AI Search": "Search across your documents to find relevant information.",
    "AI Chat": "Ask questions about your documents in natural language.",
    Account: "Manage your profile and account security.",
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
    const [activeChatId, setActiveChatId] = useState(null);

    const [uploadState, setUploadState] = useState({ active: false, fileName: "", index: 0, total: 0 });
    const [notice, setNotice] = useState(null);
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
            listChats()
                .then((data) => setChats(Array.isArray(data) ? data : []))
                .catch((error) => setNotice({ type: "error", text: error.message })),
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
    // UPLOAD
    // ============================================================

    const uploadFiles = async (files) => {
        if (files.length === 0 || uploadState.active) {
            return;
        }

        setNotice(null);

        const problems = [];
        let uploadedCount = 0;

        for (const [index, file] of files.entries()) {
            const extension = fileExtension(file.name);

            if (!SUPPORTED_EXTENSIONS.includes(extension)) {
                problems.push(`${file.name}: unsupported file type`);
                continue;
            }

            if (file.size > MAX_UPLOAD_SIZE) {
                problems.push(`${file.name}: exceeds the 10 MB limit`);
                continue;
            }

            setUploadState({ active: true, fileName: file.name, index: index + 1, total: files.length });

            try {
                const result = await uploadDocument(file);

                if (result.status === "failed") {
                    problems.push(`${file.name}: ${result.message || "processing failed"}`);
                } else {
                    uploadedCount += 1;
                }
            } catch (error) {
                problems.push(`${file.name}: ${error.message}`);
            }

            await refreshDocuments();
        }

        setUploadState({ active: false, fileName: "", index: 0, total: 0 });

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

    // ============================================================
    // DERIVED VALUES
    // ============================================================
    const completedDocuments = documents.filter((doc) => doc.status === "completed");
    const selectedDocument = documents.find((doc) => doc.id === selectedDocumentId);
    const filteredDocuments = documents.filter(
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
                        <img className="brand-logo" src={logoLight} alt="DocuMind AI" />
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
                    <div className={`api-status api-status-${apiStatus}`}>
                        <span className="status-dot" />
                        {apiStatusLabels[apiStatus]}
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
                            onBack={() => setSelectedDocumentId(null)}
                            onChanged={refreshDocuments}
                            onDeleted={() => {
                                setSelectedDocumentId(null);
                                setNotice({ type: "success", text: "Document deleted successfully." });
                                refreshDocuments();
                            }}
                            onSearch={(documentId) => startSearch("", documentId)}
                            onChatCreated={async (chat) => {
                                await refreshChats();
                                openChat(chat.id);
                            }}
                        />
                    )}

                    {activePage === "Documents" && !selectedDocument && (
                        <DocumentTable
                            documents={filteredDocuments}
                            allDocuments={documents}
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
                            chats={chats}
                            documents={documents}
                            activeChatId={activeChatId}
                            onSelectChat={setActiveChatId}
                            onChatsChanged={refreshChats}
                            onOpenDocument={openDocument}
                            onUploadClick={() => fileInputRef.current?.click()}
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
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Dashboard;
