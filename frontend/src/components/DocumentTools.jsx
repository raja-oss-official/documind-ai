// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import Icon from "./Icons.jsx";
import Select from "./Select.jsx";
import Markdown from "./Markdown.jsx";
import { compareDocuments, extractFacts, generateStudySet } from "../api.js";
import { downloadTextFile, safeFilename } from "../exportChat.js";

// ============================================================
// TABS AND LABELS
// ============================================================
const tabs = [
    { value: "quiz", label: "Quiz", icon: "check" },
    { value: "flashcards", label: "Flashcards", icon: "layers" },
    { value: "facts", label: "Key facts", icon: "note" },
    { value: "compare", label: "Compare", icon: "documents" },
];

const factLabels = {
    date: "Date",
    deadline: "Deadline",
    amount: "Amount",
    person: "Person",
    organization: "Organization",
    location: "Location",
    other: "Other",
};

// ============================================================
// CSV
// ============================================================
// Quotes every cell, and prefixes cells that start with = + - @
// so spreadsheet apps do not run them as formulas.
function toCsv(rows) {
    const cell = (value) => {
        let text = String(value ?? "");

        if (/^[=+\-@]/.test(text)) {
            text = `'${text}`;
        }

        return `"${text.replace(/"/g, '""')}"`;
    };

    return rows.map((row) => row.map(cell).join(",")).join("\r\n");
}

// ============================================================
// QUIZ
// ============================================================
function Quiz({ items, onRestart }) {
    const [answers, setAnswers] = useState({});
    const answered = Object.keys(answers).length;
    const correct = items.filter((item, index) => answers[index] === item.answer_index).length;

    return (
        <div className="quiz">
            {items.map((item, index) => {
                const chosen = answers[index];
                const done = chosen !== undefined;

                return (
                    <div className="quiz-question" key={index}>
                        <div className="quiz-number">Question {index + 1}</div>
                        <p>{item.question}</p>
                        <div className="quiz-options">
                            {item.options.map((option, optionIndex) => (
                                <button
                                    key={optionIndex}
                                    className={[
                                        done && optionIndex === item.answer_index ? "is-correct" : "",
                                        done && optionIndex === chosen && chosen !== item.answer_index ? "is-wrong" : "",
                                    ].join(" ")}
                                    onClick={() => !done && setAnswers((current) => ({ ...current, [index]: optionIndex }))}
                                    disabled={done}
                                >
                                    <span className="quiz-letter">{"ABCD"[optionIndex]}</span>
                                    {option}
                                </button>
                            ))}
                        </div>
                        {done && (
                            <p className="quiz-explanation">
                                <strong>{chosen === item.answer_index ? "Correct." : "Not quite."}</strong>{" "}
                                {item.explanation}
                                {item.page_number ? ` (page ${item.page_number})` : ""}
                            </p>
                        )}
                    </div>
                );
            })}

            <div className="tool-footer">
                <span className="muted">
                    {answered === items.length
                        ? `You got ${correct} of ${items.length} correct.`
                        : `${answered} of ${items.length} answered`}
                </span>
                <button className="button button-small" onClick={onRestart}>
                    New quiz
                </button>
            </div>
        </div>
    );
}

// ============================================================
// FLASHCARDS
// ============================================================
function Flashcards({ items, onRestart }) {
    const [index, setIndex] = useState(0);
    const [flipped, setFlipped] = useState(false);
    const card = items[index];

    const go = (step) => {
        setIndex((current) => (current + step + items.length) % items.length);
        setFlipped(false);
    };

    return (
        <div className="flashcards">
            <button
                className={`flashcard ${flipped ? "is-flipped" : ""}`}
                onClick={() => setFlipped((value) => !value)}
                aria-label={flipped ? "Show the front" : "Show the answer"}
            >
                <span className="flashcard-side">{flipped ? "Answer" : "Card"}</span>
                <span className="flashcard-text">{flipped ? card.back : card.front}</span>
                <span className="flashcard-hint">{flipped ? "Click to see the front" : "Click to flip"}</span>
            </button>

            <div className="tool-footer">
                <button className="button button-small" onClick={() => go(-1)}>
                    <Icon name="arrowLeft" /> Previous
                </button>
                <span className="muted">
                    Card {index + 1} of {items.length}
                </span>
                <button className="button button-small" onClick={() => go(1)}>
                    Next <Icon name="arrowRight" />
                </button>
                <button className="link-button" onClick={onRestart}>
                    New set
                </button>
            </div>
        </div>
    );
}

// ============================================================
// KEY FACTS TABLE
// ============================================================
function FactsTable({ document, facts, onRestart }) {
    const [category, setCategory] = useState("all");
    const present = [...new Set(facts.map((fact) => fact.category))];
    const visible = facts.filter((fact) => category === "all" || fact.category === category);

    const download = () =>
        downloadTextFile(
            safeFilename(`${document.filename.replace(/\.[^.]+$/, "")} key facts`, "csv"),
            toCsv([
                ["Category", "Value", "Context", "Page"],
                ...facts.map((fact) => [factLabels[fact.category], fact.value, fact.context, fact.page_number ?? ""]),
            ]),
            "text/csv"
        );

    if (facts.length === 0) {
        return (
            <div className="tool-footer">
                <span className="muted">No dates, amounts, names or deadlines were found.</span>
                <button className="button button-small" onClick={onRestart}>
                    Try again
                </button>
            </div>
        );
    }

    return (
        <div className="facts">
            <div className="tool-footer">
                <Select
                    ariaLabel="Fact type"
                    value={category}
                    onChange={setCategory}
                    options={[
                        { value: "all", label: `All facts (${facts.length})` },
                        ...present.map((value) => ({
                            value,
                            label: `${factLabels[value]} (${facts.filter((fact) => fact.category === value).length})`,
                        })),
                    ]}
                />
                <button className="button button-small" onClick={download}>
                    <Icon name="download" /> Download CSV
                </button>
            </div>

            <div className="md-table">
                <table>
                    <thead>
                        <tr>
                            <th>Type</th>
                            <th>Value</th>
                            <th>Context</th>
                            <th>Page</th>
                        </tr>
                    </thead>
                    <tbody>
                        {visible.map((fact, index) => (
                            <tr key={index}>
                                <td>
                                    <span className={`fact-tag fact-${fact.category}`}>{factLabels[fact.category]}</span>
                                </td>
                                <td>
                                    <strong>{fact.value}</strong>
                                </td>
                                <td>{fact.context}</td>
                                <td>{fact.page_number ?? "—"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// ============================================================
// DOCUMENT TOOLS PANEL
// ============================================================
function DocumentTools({ document, documents }) {
    // ============================================================
    // STATE
    // ============================================================
    const [tab, setTab] = useState("quiz");
    const [count, setCount] = useState(8);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [results, setResults] = useState({});
    const [compareWith, setCompareWith] = useState("");
    const [focus, setFocus] = useState("");

    const otherDocuments = documents.filter((doc) => doc.status === "completed" && doc.id !== document.id);
    const result = results[tab];

    // ============================================================
    // RUN A TOOL
    // ============================================================
    const run = async () => {
        setBusy(true);
        setError("");

        try {
            let data;

            if (tab === "quiz" || tab === "flashcards") {
                data = (await generateStudySet(document.id, tab, count)).items;
            } else if (tab === "facts") {
                data = (await extractFacts(document.id)).facts;
            } else {
                data = await compareDocuments([document.id, compareWith], focus.trim());
            }

            setResults((current) => ({ ...current, [tab]: data }));
        } catch (err) {
            setError(err.message);
        } finally {
            setBusy(false);
        }
    };

    const reset = () => setResults((current) => ({ ...current, [tab]: undefined }));

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="summary-section tools-section">
            <div className="summary-heading">
                <div>
                    <div className="section-title">
                        <Icon name="sparkles" size={16} className="title-icon" />
                        AI tools
                    </div>
                    <p className="muted">Study, extract facts, or compare with another document.</p>
                </div>
                <div className="segmented" role="tablist">
                    {tabs.map((item) => (
                        <button
                            key={item.value}
                            role="tab"
                            aria-selected={tab === item.value}
                            className={tab === item.value ? "active" : ""}
                            onClick={() => {
                                setTab(item.value);
                                setError("");
                            }}
                        >
                            <Icon name={item.icon} size={13} /> {item.label}
                        </button>
                    ))}
                </div>
            </div>

            {error && (
                <div className="notice notice-error" role="alert">
                    {error}
                </div>
            )}

            {/* ============================================================
                START A TOOL
                ============================================================ */}
            {!result && (
                <div className="tool-start">
                    {(tab === "quiz" || tab === "flashcards") && (
                        <>
                            <p className="muted">
                                {tab === "quiz"
                                    ? "Multiple-choice questions on the most important ideas, with explanations."
                                    : "Flip cards for key terms, definitions and facts."}
                            </p>
                            <div className="option-field">
                                <span>{tab === "quiz" ? "Questions" : "Cards"}</span>
                                <Select
                                    ariaLabel="How many"
                                    value={count}
                                    onChange={setCount}
                                    options={[5, 8, 12].map((value) => ({ value, label: String(value) }))}
                                />
                            </div>
                        </>
                    )}

                    {tab === "facts" && (
                        <p className="muted">
                            Dates, deadlines, amounts, people, organizations and places, in a table you can download as
                            CSV.
                        </p>
                    )}

                    {tab === "compare" &&
                        (otherDocuments.length === 0 ? (
                            <p className="muted">Upload another document to compare it with this one.</p>
                        ) : (
                            <div className="compare-form">
                                <div className="option-field">
                                    <span>Compare with</span>
                                    <Select
                                        ariaLabel="Document to compare with"
                                        value={compareWith}
                                        onChange={setCompareWith}
                                        options={[
                                            { value: "", label: "Choose a document" },
                                            ...otherDocuments.map((doc) => ({ value: doc.id, label: doc.filename })),
                                        ]}
                                    />
                                </div>
                                <input
                                    className="text-input"
                                    value={focus}
                                    onChange={(event) => setFocus(event.target.value)}
                                    placeholder="Optional focus, e.g. pricing or deadlines"
                                    maxLength={500}
                                />
                            </div>
                        ))}

                    <button
                        className="button button-primary"
                        onClick={run}
                        disabled={busy || (tab === "compare" && !compareWith)}
                    >
                        {busy ? <span className="spinner spinner-light" /> : <Icon name="sparkles" />}
                        {busy
                            ? "Working..."
                            : { quiz: "Create quiz", flashcards: "Create flashcards", facts: "Extract facts", compare: "Compare" }[tab]}
                    </button>
                </div>
            )}

            {/* ============================================================
                RESULTS
                ============================================================ */}
            {result && tab === "quiz" && <Quiz items={result} onRestart={reset} />}
            {result && tab === "flashcards" && <Flashcards items={result} onRestart={reset} />}
            {result && tab === "facts" && <FactsTable document={document} facts={result} onRestart={reset} />}
            {result && tab === "compare" && (
                <div className="compare-result">
                    <Markdown text={result.answer} />
                    <div className="tool-footer">
                        <span className="muted">
                            {result.documents.map((doc) => doc.filename).join(" vs ")}
                        </span>
                        <button className="button button-small" onClick={reset}>
                            New comparison
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default DocumentTools;
