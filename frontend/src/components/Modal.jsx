// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useId, useRef } from "react";
import Icon from "./Icons.jsx";

// ============================================================
// MODAL (DIALOG WITH BACKDROP)
// ============================================================
// Closes on Escape or a backdrop click and returns focus to the
// element that opened it.
function Modal({ title, subtitle, onClose, children, footer, size = "default" }) {
    const titleId = useId();
    const closeRef = useRef(null);
    const onCloseRef = useRef(onClose);

    useEffect(() => {
        onCloseRef.current = onClose;
    });

    // ============================================================
    // FOCUS AND ESCAPE KEY
    // ============================================================
    useEffect(() => {
        const opener = document.activeElement;
        closeRef.current?.focus();

        const handleKey = (event) => {
            if (event.key === "Escape") {
                event.stopPropagation();
                onCloseRef.current();
            }
        };

        document.addEventListener("keydown", handleKey);

        return () => {
            document.removeEventListener("keydown", handleKey);
            opener?.focus?.();
        };
    }, []);

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
            <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
                <header className="modal-header">
                    <div>
                        <h2 id={titleId}>{title}</h2>
                        {subtitle && <div className="modal-subtitle">{subtitle}</div>}
                    </div>
                    <button ref={closeRef} className="cb-icon-button" onClick={onClose} title="Close (Esc)">
                        <Icon name="close" size={16} />
                    </button>
                </header>
                <div className="modal-body">{children}</div>
                {footer && <footer className="modal-footer">{footer}</footer>}
            </div>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Modal;
