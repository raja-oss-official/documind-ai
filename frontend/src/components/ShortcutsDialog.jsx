// ============================================================
// IMPORTS
// ============================================================
import Modal from "./Modal.jsx";

// ============================================================
// SHORTCUT LIST
// ============================================================
const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

const shortcuts = [
    { keys: [isMac ? "⌘" : "Ctrl", "K"], label: "Open AI Search" },
    { keys: ["/"], label: "Focus the search or message box" },
    { keys: ["N"], label: "Start a new chat" },
    { keys: ["U"], label: "Upload documents" },
    { keys: ["1", "–", "5"], label: "Go to Dashboard, Documents, AI Search, AI Chat, Account" },
    { keys: ["T"], label: "Switch light / dark theme" },
    { keys: ["?"], label: "Show these shortcuts" },
    { keys: ["Esc"], label: "Close a dialog" },
];

// ============================================================
// KEYBOARD SHORTCUTS DIALOG
// ============================================================
function ShortcutsDialog({ onClose }) {
    return (
        <Modal title="Keyboard shortcuts" subtitle="Single-key shortcuts work when you are not typing." onClose={onClose}>
            <ul className="shortcut-list">
                {shortcuts.map((shortcut) => (
                    <li key={shortcut.label}>
                        <span>{shortcut.label}</span>
                        <span className="shortcut-keys">
                            {shortcut.keys.map((key, index) =>
                                key === "–" ? <span key={index}>–</span> : <kbd key={index}>{key}</kbd>
                            )}
                        </span>
                    </li>
                ))}
            </ul>
        </Modal>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default ShortcutsDialog;
