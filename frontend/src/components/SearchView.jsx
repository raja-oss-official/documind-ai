// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import Select from "./Select.jsx";
import { askDocuments, searchDocuments } from "../api.js";
import SourceList from "./SourceList.jsx";

// ============================================================
// AI SEARCH PAGE
// ============================================================
function SearchView({ documents, pendingSearch, onPendingConsumed, onOpenDocument }) {
    // ============================================================
    // STATE
    // ============================================================
    const [query, setQuery] = useState(pendingSearch?.query || "");
    const [documentId, setDocumentId] = useState(pendingSearch?.documentId || "");
    const [limit, setLimit] = useState(5);
    const [loading, setLoading] = useState(pendingSearch?.query ? "search" : "");
    const [error, setError] = useState("");
    const [results, setResults] = useState(null);
    const [answer, setAnswer] = useState(null);
    const handledSearchId = useRef(null);

    const completedDocuments = documents.filter((doc) => doc.status === "completed");

    // ============================================================
    // SEARCH AND ASK
    // ============================================================
    const fetchResults = (searchQuery, searchDocumentId) =>
        searchDocuments({ query: searchQuery, documentId: searchDocumentId, limit })
            .then(setResults)
            .catch((err) => {
                setError(err.message);
                setResults(null);
            })
            .finally(() => setLoading(""));

    const runSearch = (searchQuery, searchDocumentId) => {
        setLoading("search");
        setError("");
        setAnswer(null);
        fetchResults(searchQuery, searchDocumentId);
    };

    const runAsk = async () => {
        setLoading("ask");
        setError("");
        setResults(null);

        try {
            setAnswer(await askDocuments(query.trim()));
        } catch (err) {
            setError(err.message);
            setAnswer(null);
        } finally {
            setLoading("");
        }
    };

    // ============================================================
    // SEARCH STARTED FROM ANOTHER PAGE
    // ============================================================
    // Searches started from the dashboard or a document page. The view is
    // mounted fresh for them, so query and filter come from initial state.
    useEffect(() => {
        if (!pendingSearch || handledSearchId.current === pendingSearch.id) {
            return;
        }

        handledSearchId.current = pendingSearch.id;
        onPendingConsumed();

        if (pendingSearch.query) {
            fetchResults(pendingSearch.query, pendingSearch.documentId);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ============================================================
    // RENDER
    // ============================================================
    const canSubmit = query.trim().length > 0 && !loading;

    return (
        <div className="panel tool-panel">
            <h2>Search your documents</h2>
            <p className="muted">
                Semantic search finds passages by meaning, not just matching words. Use
                “Ask AI” to get a written answer drawn from all of your documents.
            </p>

            {/* ============================================================
                SEARCH BOX
                ============================================================ */}
            <form
                className="search-form"
                onSubmit={(event) => {
                    event.preventDefault();

                    if (canSubmit) {
                        runSearch(query.trim(), documentId);
                    }
                }}
            >
                <Icon name="search" size={18} className="search-icon" />
                <input
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="What are you looking for?"
                    maxLength={500}
                    autoFocus
                />
                <button className="button button-primary" type="submit" disabled={!canSubmit}>
                    <Icon name="search" /> {loading === "search" ? "Searching..." : "Search"}
                </button>
                <button
                    className="button"
                    type="button"
                    onClick={runAsk}
                    disabled={!canSubmit}
                    title="Answer from all documents"
                >
                    <Icon name="sparkles" /> {loading === "ask" ? "Thinking..." : "Ask AI"}
                </button>
            </form>

            {/* ============================================================
                SEARCH OPTIONS
                ============================================================ */}
            <div className="search-options">
                <div className="option-field">
                    <span>Document</span>
                    <Select
                        ariaLabel="Document"
                        value={documentId}
                        onChange={setDocumentId}
                        options={[
                            { value: "", label: "All documents" },
                            ...completedDocuments.map((doc) => ({ value: doc.id, label: doc.filename })),
                        ]}
                    />
                </div>
                <div className="option-field">
                    <span>Results</span>
                    <Select
                        ariaLabel="Number of results"
                        value={limit}
                        onChange={setLimit}
                        options={[5, 10, 20].map((value) => ({ value, label: String(value) }))}
                    />
                </div>
            </div>

            {/* ============================================================
                ERROR AND LOADING
                ============================================================ */}
            {error && (
                <div className="notice notice-error" role="alert">
                    {error}
                </div>
            )}

            {loading && (
                <p className="muted">
                    <span className="spinner" />{" "}
                    {loading === "ask"
                        ? "Reading your documents and writing an answer..."
                        : "Searching your documents..."}
                </p>
            )}

            {/* ============================================================
                AI ANSWER
                ============================================================ */}
            {answer && !loading && (
                <div className="search-results">
                    <div className="answer-card">
                        <div className="sub-heading">AI ANSWER</div>
                        <p className="answer-text">{answer.answer}</p>
                    </div>
                    {answer.sources?.length > 0 && (
                        <>
                            <div className="sub-heading">SOURCES</div>
                            <SourceList
                                sources={answer.sources}
                                documents={documents}
                                onOpenDocument={onOpenDocument}
                                compact
                            />
                        </>
                    )}
                </div>
            )}

            {/* ============================================================
                SEARCH RESULTS
                ============================================================ */}
            {results && !loading && (
                <div className="search-results">
                    <div className="sub-heading">
                        {results.result_count} {results.result_count === 1 ? "RESULT" : "RESULTS"} FOR
                        “{results.query}”
                    </div>
                    {results.result_count === 0 ? (
                        <p className="muted">
                            No relevant passages found. Try different wording or search all
                            documents.
                        </p>
                    ) : (
                        <SourceList
                            sources={results.results}
                            documents={documents}
                            onOpenDocument={onOpenDocument}
                        />
                    )}
                </div>
            )}
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default SearchView;
