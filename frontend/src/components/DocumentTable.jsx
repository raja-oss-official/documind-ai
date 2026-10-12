// ============================================================
// IMPORTS
// ============================================================
import { formatFileSize, formatRelativeTime } from "../api.js";
import Icon from "./Icons.jsx";
import { FileIcon, StatusBadge } from "./DocumentBadges.jsx";

// ============================================================
// STATUS FILTER TABS
// ============================================================
const statusTabs = [
    { value: "all", label: "All" },
    { value: "completed", label: "Processed" },
    { value: "failed", label: "Failed" },
];

// ============================================================
// DOCUMENTS TABLE
// ============================================================
function DocumentTable({
    documents,
    allDocuments,
    loading,
    error,
    onRetry,
    onOpen,
    onUploadClick,
    filter,
    onFilterChange,
    statusFilter,
    onStatusFilterChange,
}) {
    // ============================================================
    // COUNTS
    // ============================================================
    const countFor = (status) =>
        status === "all"
            ? allDocuments.length
            : allDocuments.filter((doc) => doc.status === status).length;

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="panel documents-panel">
            {/* ============================================================
                FILTERS
                ============================================================ */}
            <div className="panel-header">
                <div className="segmented">
                    {statusTabs.map((tab) => (
                        <button
                            key={tab.value}
                            className={statusFilter === tab.value ? "active" : ""}
                            onClick={() => onStatusFilterChange(tab.value)}
                        >
                            {tab.label}
                            <span>{countFor(tab.value)}</span>
                        </button>
                    ))}
                </div>
                <div className="filter-field">
                    <Icon name="search" size={15} />
                    <input
                        value={filter}
                        onChange={(event) => onFilterChange(event.target.value)}
                        placeholder="Filter by name..."
                    />
                </div>
            </div>

            {/* ============================================================
                TABLE
                ============================================================ */}
            <div className="document-table">
                <div className="table-row table-heading">
                    <span>DOCUMENT</span>
                    <span>PAGES</span>
                    <span>SIZE</span>
                    <span>UPLOADED</span>
                    <span>STATUS</span>
                </div>

                {/* ============================================================
                    DOCUMENT ROWS
                    ============================================================ */}
                {documents.map((document) => (
                    <button
                        className="table-row table-row-button"
                        key={document.id}
                        onClick={() => onOpen(document.id)}
                    >
                        <div className="document-name">
                            <FileIcon filename={document.filename} />
                            <span>
                                {document.filename}
                                {document.summary && (
                                    <span className="summary-flag">
                                        <Icon name="sparkles" size={11} /> Summary
                                    </span>
                                )}
                            </span>
                        </div>
                        <span className="file-type">{document.page_count || "—"}</span>
                        <span className="file-size">{formatFileSize(document.file_size)}</span>
                        <span className="file-type">{formatRelativeTime(document.created_at)}</span>
                        <span>
                            <StatusBadge status={document.status} />
                        </span>
                    </button>
                ))}

                {/* ============================================================
                    LOADING, ERROR AND EMPTY STATES
                    ============================================================ */}
                {loading && <div className="empty-state">Loading documents...</div>}

                {!loading && error && (
                    <div className="empty-state">
                        {error}{" "}
                        <button className="link-button" onClick={onRetry}>
                            Try again
                        </button>
                    </div>
                )}

                {!loading && !error && documents.length === 0 && (
                    <div className="empty-state">
                        <div className="empty-icon">
                            <Icon name={allDocuments.length === 0 ? "upload" : "search"} size={22} />
                        </div>
                        <strong>
                            {allDocuments.length === 0 ? "No documents yet" : "No matching documents"}
                        </strong>
                        <span>
                            {allDocuments.length === 0
                                ? "Drop files anywhere on this page, or upload a PDF, DOCX, TXT, CSV, XLSX, PPTX, or image."
                                : "Try a different name or status."}
                        </span>
                        {allDocuments.length === 0 && (
                            <button className="button button-primary empty-action" onClick={onUploadClick}>
                                <Icon name="upload" /> Upload documents
                            </button>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default DocumentTable;
