// ============================================================
// IMPORTS
// ============================================================
import { fileExtension, isVideo } from "../api.js";
import Icon from "./Icons.jsx";

// ============================================================
// CONFIGURATION
// ============================================================
const UPLOAD_DAYS = 14;
const TOP_ITEMS = 5;

// ============================================================
// HELPERS
// ============================================================
// Backend datetimes are UTC; naive ISO strings need a "Z".
function parseDate(value) {
    const text = String(value || "");
    return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(text) ? text : `${text}Z`);
}

const dayKey = (date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

const shortDay = (date) => date.toLocaleDateString([], { month: "short", day: "numeric" });

function uploadsPerDay(documents) {
    const days = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    for (let offset = UPLOAD_DAYS - 1; offset >= 0; offset -= 1) {
        const date = new Date(today);
        date.setDate(today.getDate() - offset);
        days.push({ date, key: dayKey(date), count: 0 });
    }

    const byKey = Object.fromEntries(days.map((day) => [day.key, day]));

    for (const doc of documents) {
        const day = byKey[dayKey(parseDate(doc.created_at))];

        if (day) {
            day.count += 1;
        }
    }

    return days;
}

function countBy(items, getKey) {
    const counts = {};

    for (const item of items) {
        const key = getKey(item);

        if (key) {
            counts[key] = (counts[key] || 0) + 1;
        }
    }

    return Object.entries(counts)
        .map(([label, value]) => ({ label, value }))
        .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

// ============================================================
// HORIZONTAL BAR LIST (VALUE AT THE TIP)
// ============================================================
function BarList({ items, unit, onSelect }) {
    const max = Math.max(1, ...items.map((item) => item.value));

    return (
        <ul className="insight-bars">
            {items.map((item) => {
                const content = (
                    <>
                        <span className="insight-bar-label" title={item.label}>
                            {item.label}
                        </span>
                        <span className="insight-bar-track">
                            <span className="insight-bar-fill" style={{ width: `${(item.value / max) * 100}%` }} />
                            <span className="insight-bar-value">
                                {item.value} <span className="sr-only">{unit(item.value)}</span>
                            </span>
                        </span>
                    </>
                );

                return (
                    <li key={item.label}>
                        {onSelect && item.id ? (
                            <button className="insight-bar-row" onClick={() => onSelect(item.id)}>
                                {content}
                            </button>
                        ) : (
                            <div className="insight-bar-row">{content}</div>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}

// ============================================================
// WORKSPACE INSIGHTS
// ============================================================
function Insights({ documents, chats, onOpenDocument }) {
    if (documents.length === 0) {
        return null;
    }

    // ============================================================
    // DERIVED DATA
    // ============================================================
    const days = uploadsPerDay(documents);
    const recentUploads = days.reduce((total, day) => total + day.count, 0);
    const maxDay = Math.max(1, ...days.map((day) => day.count));
    const peak = days.reduce((best, day) => (day.count > best.count ? day : best), days[0]);

    const types = countBy(documents, (doc) =>
        isVideo(doc) ? "YOUTUBE" : fileExtension(doc.filename).replace(".", "").toUpperCase() || "OTHER"
    );

    const names = Object.fromEntries(documents.map((doc) => [doc.id, doc.filename]));
    const discussed = countBy(
        chats.filter((chat) => names[chat.document_id]),
        (chat) => chat.document_id
    )
        .slice(0, TOP_ITEMS)
        .map((item) => ({ id: item.label, label: names[item.label], value: item.value }));
    const unlinkedChats = chats.filter((chat) => !chat.document_id).length;

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="panel insights-panel">
            <div className="panel-header">
                <div>
                    <div className="section-title">
                        <Icon name="chart" size={16} className="title-icon" />
                        Workspace insights
                    </div>
                    <p className="muted">How your documents and conversations are growing.</p>
                </div>
            </div>

            <div className="insights-grid">
                {/* ============================================================
                    UPLOADS PER DAY (COLUMN CHART)
                    ============================================================ */}
                <section className="insight">
                    <h3>Uploads, last {UPLOAD_DAYS} days</h3>
                    <p className="insight-figure">
                        <strong>{recentUploads}</strong> {recentUploads === 1 ? "document" : "documents"}
                    </p>

                    <div className="insight-columns" aria-hidden="true">
                        {days.map((day) => (
                            <div className="insight-column" key={day.key}>
                                {day === peak && day.count > 0 && (
                                    <span
                                        className="insight-column-peak"
                                        style={{ bottom: `${(day.count / maxDay) * 100}%` }}
                                    >
                                        {day.count}
                                    </span>
                                )}
                                {day.count > 0 && (
                                    <span className="insight-column-fill" style={{ height: `${(day.count / maxDay) * 100}%` }} />
                                )}
                                <span className="insight-tooltip">
                                    <strong>{shortDay(day.date)}</strong>
                                    {day.count} {day.count === 1 ? "upload" : "uploads"}
                                </span>
                            </div>
                        ))}
                    </div>
                    <div className="insight-axis" aria-hidden="true">
                        <span>{shortDay(days[0].date)}</span>
                        <span>Today</span>
                    </div>

                    {/* Screen-reader table with every value. */}
                    <table className="sr-only">
                        <caption>Uploads per day, last {UPLOAD_DAYS} days</caption>
                        <thead>
                            <tr>
                                <th>Day</th>
                                <th>Uploads</th>
                            </tr>
                        </thead>
                        <tbody>
                            {days.map((day) => (
                                <tr key={day.key}>
                                    <td>{shortDay(day.date)}</td>
                                    <td>{day.count}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </section>

                {/* ============================================================
                    DOCUMENTS BY TYPE
                    ============================================================ */}
                <section className="insight">
                    <h3>Documents by type</h3>
                    <p className="insight-figure">
                        <strong>{types.length}</strong> {types.length === 1 ? "file type" : "file types"}
                    </p>
                    <BarList items={types} unit={(value) => (value === 1 ? "document" : "documents")} />
                </section>

                {/* ============================================================
                    MOST DISCUSSED DOCUMENTS
                    ============================================================ */}
                <section className="insight">
                    <h3>Most discussed documents</h3>
                    <p className="insight-figure">
                        <strong>{chats.length}</strong> {chats.length === 1 ? "chat" : "chats"}
                        {unlinkedChats > 0 && <span> · {unlinkedChats} across all documents</span>}
                    </p>
                    {discussed.length > 0 ? (
                        <BarList
                            items={discussed}
                            unit={(value) => (value === 1 ? "chat" : "chats")}
                            onSelect={onOpenDocument}
                        />
                    ) : (
                        <p className="muted insight-empty">
                            Start a chat from a document page to see which documents you discuss most.
                        </p>
                    )}
                </section>
            </div>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Insights;
