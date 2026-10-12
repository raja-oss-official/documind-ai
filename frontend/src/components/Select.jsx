// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useId, useRef, useState } from "react";
import Icon from "./Icons.jsx";

// ============================================================
// SELECT (CUSTOM DROPDOWN)
// ============================================================
// Custom dropdown so the open menu matches the workspace style
// (native <select> menus are drawn by the OS and cannot be styled).
function Select({ value, options, onChange, disabled = false, variant = "default", ariaLabel, title }) {
    // ============================================================
    // STATE
    // ============================================================
    const [open, setOpen] = useState(false);
    const [activeIndex, setActiveIndex] = useState(-1);
    const rootRef = useRef(null);
    const listId = useId();

    const selected = options.find((option) => option.value === value);

    // ============================================================
    // CLOSE ON OUTSIDE CLICK
    // ============================================================
    useEffect(() => {
        if (!open) {
            return;
        }

        const handlePointer = (event) => {
            if (!rootRef.current?.contains(event.target)) {
                setOpen(false);
            }
        };

        document.addEventListener("mousedown", handlePointer);
        return () => document.removeEventListener("mousedown", handlePointer);
    }, [open]);

    // ============================================================
    // OPEN AND CHOOSE
    // ============================================================
    const openMenu = () => {
        setActiveIndex(Math.max(0, options.findIndex((option) => option.value === value)));
        setOpen(true);
    };

    const choose = (option) => {
        setOpen(false);

        if (option.value !== value) {
            onChange(option.value);
        }
    };

    // ============================================================
    // KEYBOARD SUPPORT
    // ============================================================
    const handleKeyDown = (event) => {
        if (disabled) {
            return;
        }

        if (!open) {
            if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
                event.preventDefault();
                openMenu();
            }
            return;
        }

        if (event.key === "Escape" || event.key === "Tab") {
            setOpen(false);
        } else if (event.key === "ArrowDown") {
            event.preventDefault();
            setActiveIndex((index) => Math.min(options.length - 1, index + 1));
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            setActiveIndex((index) => Math.max(0, index - 1));
        } else if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();

            if (options[activeIndex]) {
                choose(options[activeIndex]);
            }
        }
    };

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className={`select select-${variant} ${open ? "is-open" : ""}`} ref={rootRef}>
            <button
                type="button"
                className="select-trigger"
                onClick={() => (open ? setOpen(false) : openMenu())}
                onKeyDown={handleKeyDown}
                disabled={disabled}
                aria-haspopup="listbox"
                aria-expanded={open}
                aria-controls={listId}
                aria-label={ariaLabel}
                title={title}
            >
                <span className="select-value">{selected?.label ?? "Select..."}</span>
                <Icon name="chevronDown" size={14} className="select-chevron" />
            </button>

            {/* ============================================================
                OPTIONS MENU
                ============================================================ */}
            {open && (
                <ul className="select-menu" role="listbox" id={listId}>
                    {options.map((option, index) => (
                        <li
                            key={option.value}
                            role="option"
                            aria-selected={option.value === value}
                            className={`${index === activeIndex ? "is-active" : ""} ${
                                option.value === value ? "is-selected" : ""
                            }`}
                            onMouseEnter={() => setActiveIndex(index)}
                            onMouseDown={(event) => event.preventDefault()}
                            onClick={() => choose(option)}
                        >
                            <span>{option.label}</span>
                            {option.value === value && <Icon name="checkMark" size={14} />}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Select;
