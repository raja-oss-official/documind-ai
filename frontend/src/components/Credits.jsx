// ============================================================
// CREDITS (DEVELOPER AND PROJECT)
// ============================================================
// Shown at the bottom of the sign-in page and the workspace.
// `variant="dark"` is used on the navy brand panel.
function Credits({ variant = "light" }) {
    return (
        <div className={`credits credits-${variant}`}>
            <span className="credits-author">
                Developed by <strong>Raja Sundaram R S</strong>
            </span>
            <span className="credits-badge">Hexaware Internship Project</span>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default Credits;
