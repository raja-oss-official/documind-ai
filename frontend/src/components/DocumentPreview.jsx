// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useState } from "react";
import Icon from "./Icons.jsx";
import Modal from "./Modal.jsx";
import { fileExtension, getDocumentFile, isVideo, parseTimestamp } from "../api.js";

// ============================================================
// PREVIEW KINDS
// ============================================================
// Browsers can show PDFs, images and text. Word, Excel and
// PowerPoint files are offered as a download instead.
function previewKind(filename) {
    const extension = fileExtension(filename);

    if (extension === ".pdf") return "pdf";
    if ([".png", ".jpg", ".jpeg"].includes(extension)) return "image";
    if ([".txt", ".csv"].includes(extension)) return "text";
    return "download";
}

// ============================================================
// DOCUMENT PREVIEW (ORIGINAL FILE)
// ============================================================
// `page` opens a PDF at that page (from a cited source).
function DocumentPreview({ document, page, passage, onClose }) {
    // YouTube videos play from the cited moment instead.
    if (isVideo(document)) {
        return <VideoPreview document={document} passage={passage} onClose={onClose} />;
    }

    return <FilePreview document={document} page={page} passage={passage} onClose={onClose} />;
}

// ============================================================
// YOUTUBE VIDEO AT THE CITED MOMENT
// ============================================================
function VideoPreview({ document, passage, onClose }) {
    const start = parseTimestamp(passage) || 0;

    return (
        <Modal title={document.filename} subtitle="YouTube video" onClose={onClose} size="large">
            {passage && (
                <blockquote className="preview-passage">
                    <strong>Cited moment</strong>
                    {passage}
                </blockquote>
            )}
            <div className="yt-player">
                <iframe
                    src={`https://www.youtube-nocookie.com/embed/${document.video_id}?rel=0&start=${start}&autoplay=1`}
                    title={document.filename}
                    allow="autoplay; encrypted-media; picture-in-picture"
                    allowFullScreen
                />
            </div>
        </Modal>
    );
}

// ============================================================
// UPLOADED FILE
// ============================================================
function FilePreview({ document, page, passage, onClose }) {
    // ============================================================
    // STATE
    // ============================================================
    const [url, setUrl] = useState("");
    const [text, setText] = useState("");
    const [error, setError] = useState("");
    const kind = previewKind(document.filename);

    // ============================================================
    // FETCH THE FILE (WITH THE ACCESS TOKEN)
    // ============================================================
    useEffect(() => {
        let objectUrl = "";
        let cancelled = false;

        getDocumentFile(document.id)
            .then(async (blob) => {
                if (cancelled) return;

                if (kind === "text") {
                    setText(await blob.text());
                }

                objectUrl = URL.createObjectURL(blob);
                setUrl(objectUrl);
            })
            .catch((err) => !cancelled && setError(err.message));

        return () => {
            cancelled = true;

            if (objectUrl) {
                URL.revokeObjectURL(objectUrl);
            }
        };
    }, [document.id, kind]);

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <Modal
            title={document.filename}
            subtitle={page ? `Opened at page ${page}` : "Original file"}
            onClose={onClose}
            size="large"
            footer={
                <>
                    <span className="muted">
                        {passage ? "The cited passage is shown above the file." : "Preview of the uploaded file."}
                    </span>
                    {url && (
                        <a className="button button-small" href={url} download={document.filename}>
                            <Icon name="download" /> Download
                        </a>
                    )}
                </>
            }
        >
            {passage && (
                <blockquote className="preview-passage">
                    <strong>Cited passage{page ? ` · page ${page}` : ""}</strong>
                    {passage}
                </blockquote>
            )}

            {error && (
                <div className="notice notice-error" role="alert">
                    {error}
                </div>
            )}

            {!url && !error && (
                <p className="muted">
                    <span className="spinner" /> Loading file...
                </p>
            )}

            {url && kind === "pdf" && (
                <iframe
                    className="preview-frame"
                    title={document.filename}
                    src={`${url}#page=${page || 1}`}
                />
            )}

            {url && kind === "image" && <img className="preview-image" src={url} alt={document.filename} />}

            {url && kind === "text" && <pre className="preview-plain">{text}</pre>}

            {url && kind === "download" && (
                <div className="empty-state">
                    <div className="empty-icon">
                        <Icon name="documents" size={22} />
                    </div>
                    <strong>This file type can't be shown in the browser</strong>
                    <span>Download it to open it in Word, Excel or PowerPoint.</span>
                </div>
            )}
        </Modal>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default DocumentPreview;
