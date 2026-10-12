// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import Icon from "./Icons.jsx";

// Safe Markdown for AI answers: headings, paragraphs, bullet and numbered
// lists, fenced code blocks, tables, quotes, rules, **bold**, *italic* and
// `code`. Builds React elements only (no raw HTML).

// ============================================================
// INLINE FORMATTING (BOLD, ITALIC, CODE)
// ============================================================
function renderInline(text, keyPrefix) {
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g);

    return parts.map((part, index) => {
        const key = `${keyPrefix}-${index}`;

        // Bold and italic can wrap inline code, e.g. **`%`**.
        if (/^\*\*[^*]+\*\*$/.test(part)) {
            return <strong key={key}>{renderInline(part.slice(2, -2), key)}</strong>;
        }

        if (/^`[^`]+`$/.test(part)) {
            return <code key={key}>{part.slice(1, -1)}</code>;
        }

        if (/^\*[^*\s][^*]*\*$/.test(part)) {
            return <em key={key}>{renderInline(part.slice(1, -1), key)}</em>;
        }

        return part;
    });
}

// ============================================================
// TABLE HELPERS
// ============================================================
const splitRow = (line) =>
    line
        .trim()
        .replace(/^\|/, "")
        .replace(/\|$/, "")
        .split("|")
        .map((cell) => cell.trim());

const isTableSeparator = (line) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line || "");

// ============================================================
// BLOCK PARSER (HEADINGS, LISTS, CODE, TABLES)
// ============================================================
function parseBlocks(text) {
    const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
    const blocks = [];
    let list = null;
    let paragraph = [];

    const flushParagraph = () => {
        if (paragraph.length) {
            blocks.push({ type: "p", text: paragraph.join(" ") });
            paragraph = [];
        }
    };

    const flushList = () => {
        if (list) {
            blocks.push(list);
            list = null;
        }
    };

    for (let i = 0; i < lines.length; i += 1) {
        const rawLine = lines[i];
        const line = rawLine.trim();

        // Fenced code block (also handles a block still streaming in).
        const fence = line.match(/^```\s*([\w+-]*)/);

        if (fence) {
            flushParagraph();
            flushList();
            const code = [];
            i += 1;

            while (i < lines.length && !lines[i].trim().startsWith("```")) {
                code.push(lines[i]);
                i += 1;
            }

            blocks.push({ type: "code", language: fence[1], text: code.join("\n") });
            continue;
        }

        // Table: a header row followed by a |---| separator.
        if (line.includes("|") && isTableSeparator(lines[i + 1])) {
            flushParagraph();
            flushList();
            const header = splitRow(line);
            const rows = [];
            i += 2;

            while (i < lines.length && lines[i].trim().includes("|") && lines[i].trim()) {
                rows.push(splitRow(lines[i]));
                i += 1;
            }

            i -= 1;
            blocks.push({ type: "table", header, rows });
            continue;
        }

        const bullet = line.match(/^[-*•]\s+(.*)$/);
        const numbered = line.match(/^(\d+)[.)]\s+(.*)$/);
        const heading = line.match(/^(#{1,4})\s+(.*)$/);

        if (!line) {
            flushParagraph();
            flushList();
        } else if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) {
            flushParagraph();
            flushList();
            blocks.push({ type: "hr" });
        } else if (line.startsWith(">")) {
            flushParagraph();
            flushList();
            blocks.push({ type: "quote", text: line.replace(/^>\s?/, "") });
        } else if (bullet || numbered) {
            flushParagraph();
            const type = bullet ? "ul" : "ol";

            if (!list || list.type !== type) {
                flushList();
                list = { type, start: numbered ? Number(numbered[1]) : 1, items: [] };
            }

            list.items.push(bullet ? bullet[1] : numbered[2]);
        } else if (heading) {
            flushParagraph();
            flushList();
            blocks.push({ type: "h", level: heading[1].length, text: heading[2] });
        } else {
            flushList();
            paragraph.push(line);
        }
    }

    flushParagraph();
    flushList();
    return blocks;
}

// ============================================================
// CODE BLOCK WITH COPY BUTTON
// ============================================================
function CodeBlock({ language, text }) {
    const [copied, setCopied] = useState(false);

    const copy = async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            // Clipboard can be unavailable (insecure context); ignore.
        }
    };

    return (
        <div className="md-code">
            <div className="md-code-bar">
                <span>{language || "code"}</span>
                <button type="button" onClick={copy}>
                    <Icon name={copied ? "checkMark" : "copy"} size={12} />
                    {copied ? "Copied" : "Copy"}
                </button>
            </div>
            <pre>
                <code>{text}</code>
            </pre>
        </div>
    );
}

// ============================================================
// MARKDOWN RENDERER
// ============================================================
function Markdown({ text }) {
    const blocks = parseBlocks(text);

    return (
        <div className="markdown">
            {blocks.map((block, index) => {
                switch (block.type) {
                    case "h":
                        return block.level <= 2 ? (
                            <h3 key={index}>{renderInline(block.text, index)}</h3>
                        ) : (
                            <h4 key={index}>{renderInline(block.text, index)}</h4>
                        );
                    case "ul":
                        return (
                            <ul key={index}>
                                {block.items.map((item, itemIndex) => (
                                    <li key={itemIndex}>{renderInline(item, `${index}-${itemIndex}`)}</li>
                                ))}
                            </ul>
                        );
                    case "ol":
                        return (
                            <ol key={index} start={block.start}>
                                {block.items.map((item, itemIndex) => (
                                    <li key={itemIndex}>{renderInline(item, `${index}-${itemIndex}`)}</li>
                                ))}
                            </ol>
                        );
                    case "code":
                        return <CodeBlock key={index} language={block.language} text={block.text} />;
                    case "table":
                        return (
                            <div className="md-table" key={index}>
                                <table>
                                    <thead>
                                        <tr>
                                            {block.header.map((cell, cellIndex) => (
                                                <th key={cellIndex}>{renderInline(cell, `${index}-h${cellIndex}`)}</th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {block.rows.map((row, rowIndex) => (
                                            <tr key={rowIndex}>
                                                {row.map((cell, cellIndex) => (
                                                    <td key={cellIndex}>
                                                        {renderInline(cell, `${index}-${rowIndex}-${cellIndex}`)}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        );
                    case "quote":
                        return <blockquote key={index}>{renderInline(block.text, index)}</blockquote>;
                    case "hr":
                        return <hr key={index} />;
                    default:
                        return <p key={index}>{renderInline(block.text, index)}</p>;
                }
            })}
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Markdown;
