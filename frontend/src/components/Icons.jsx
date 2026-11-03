// ============================================================
// IMPORTS
// ============================================================
import { useId } from "react";

// Stroke icons (24px grid, Lucide-style) used across the workspace.

// ============================================================
// ICON PATHS
// ============================================================
const paths = {
    dashboard: (
        <>
            <rect x="3" y="3" width="7" height="9" rx="1.5" />
            <rect x="14" y="3" width="7" height="5" rx="1.5" />
            <rect x="14" y="12" width="7" height="9" rx="1.5" />
            <rect x="3" y="16" width="7" height="5" rx="1.5" />
        </>
    ),
    documents: (
        <>
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5Z" />
            <path d="M14 2v6h6" />
            <path d="M8 13h8M8 17h5" />
        </>
    ),
    search: (
        <>
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
        </>
    ),
    chat: (
        <>
            <path d="M21 12a8 8 0 0 1-11.6 7.1L4 20.5l1.4-4.9A8 8 0 1 1 21 12Z" />
            <path d="M8.5 12h.01M12 12h.01M15.5 12h.01" />
        </>
    ),
    user: (
        <>
            <circle cx="12" cy="8" r="4" />
            <path d="M4 21a8 8 0 0 1 16 0" />
        </>
    ),
    upload: (
        <>
            <path d="M12 15V3M7 8l5-5 5 5" />
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        </>
    ),
    plus: <path d="M12 5v14M5 12h14" />,
    layers: (
        <>
            <path d="m12 2 10 5-10 5L2 7Z" />
            <path d="m2 17 10 5 10-5M2 12l10 5 10-5" />
        </>
    ),
    link: (
        <>
            <path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7" />
            <path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7" />
        </>
    ),
    note: (
        <>
            <path d="M15.5 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.5Z" />
            <path d="M15 3v6h6M7 13h6M7 17h10" />
        </>
    ),
    logout: (
        <>
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <path d="m16 17 5-5-5-5M21 12H9" />
        </>
    ),
    check: (
        <>
            <circle cx="12" cy="12" r="9" />
            <path d="m8.5 12 2.5 2.5 4.5-5" />
        </>
    ),
    sparkles: (
        <>
            <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9Z" />
            <path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8Z" />
        </>
    ),
    trash: (
        <>
            <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" />
        </>
    ),
    pencil: (
        <>
            <path d="M17 3a2.8 2.8 0 0 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
        </>
    ),
    copy: (
        <>
            <rect x="9" y="9" width="12" height="12" rx="1" />
            <path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1" />
        </>
    ),
    paperclip: <path d="m21 11-8.6 8.6a5 5 0 0 1-7-7l8.5-8.6a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4L15.6 8" />,
    arrowUp: <path d="M12 19V5M5 12l7-7 7 7" />,
    history: (
        <>
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
            <path d="M3 3v5h5M12 7v5l3 2" />
        </>
    ),
    chevronDown: <path d="m6 9 6 6 6-6" />,
    checkMark: <path d="M20 6 9 17l-5-5" />,
    arrowLeft: <path d="M19 12H5M12 19l-7-7 7-7" />,
    arrowRight: <path d="M5 12h14M12 5l7 7-7 7" />,
    send: (
        <>
            <path d="M22 2 11 13" />
            <path d="M22 2 15 22l-4-9-9-4Z" />
        </>
    ),
    close: <path d="M18 6 6 18M6 6l12 12" />,
    lock: (
        <>
            <rect x="4" y="11" width="16" height="10" rx="2" />
            <path d="M8 11V7a4 4 0 0 1 8 0v4" />
        </>
    ),
    inbox: (
        <>
            <path d="M22 12h-6l-2 3h-4l-2-3H2" />
            <path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z" />
        </>
    ),
    download: (
        <>
            <path d="M12 3v12M7 10l5 5 5-5" />
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        </>
    ),
    printer: (
        <>
            <path d="M6 9V3h12v6" />
            <rect x="6" y="14" width="12" height="7" rx="1" />
            <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
        </>
    ),
    mic: (
        <>
            <rect x="9" y="2" width="6" height="12" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0M12 18v4M8 22h8" />
        </>
    ),
    volume: (
        <>
            <path d="M11 5 6 9H2v6h4l5 4Z" />
            <path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" />
        </>
    ),
    stop: <rect x="6" y="6" width="12" height="12" rx="1.5" />,
    star: <path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1Z" />,
    sun: (
        <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </>
    ),
    moon: <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />,
    keyboard: (
        <>
            <rect x="2" y="5" width="20" height="14" rx="2" />
            <path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M10 13h4M7 16h10" />
        </>
    ),
    eye: (
        <>
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
            <circle cx="12" cy="12" r="3" />
        </>
    ),
    clock: (
        <>
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7v5l3 2" />
        </>
    ),
    share: (
        <>
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" />
        </>
    ),
    chart: (
        <>
            <path d="M3 3v18h18" />
            <path d="M8 17v-5M13 17V8M18 17v-8" />
        </>
    ),
};

// ============================================================
// ICON COMPONENT
// ============================================================
// `gradient` draws the icon in the brand gradient (sky blue to violet).
function Icon({ name, size = 16, className = "", gradient = false, strokeWidth = 1.8 }) {
    const gradientId = useId();

    return (
        <svg
            className={`icon ${className}`}
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke={gradient ? `url(#${gradientId})` : "currentColor"}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            {gradient && (
                <defs>
                    <linearGradient id={gradientId} x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                        <stop offset="0" stopColor="#20a1fd" />
                        <stop offset="0.5" stopColor="#3d7bfb" />
                        <stop offset="1" stopColor="#615afc" />
                    </linearGradient>
                </defs>
            )}
            {paths[name]}
        </svg>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Icon;
