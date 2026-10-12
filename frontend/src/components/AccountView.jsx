// ============================================================
// IMPORTS
// ============================================================
import { useState } from "react";
import { changePassword } from "../api.js";
import Icon from "./Icons.jsx";

// ============================================================
// PASSWORD RULES
// ============================================================
const passwordRules = [
    { label: "At least 8 characters", test: (value) => value.length >= 8 },
    { label: "An uppercase letter", test: (value) => /[A-Z]/.test(value) },
    { label: "A lowercase letter", test: (value) => /[a-z]/.test(value) },
    { label: "A number", test: (value) => /\d/.test(value) },
    { label: "A special character", test: (value) => /[^A-Za-z0-9]/.test(value) },
];

// ============================================================
// ACCOUNT PAGE
// ============================================================
function AccountView({ user, documentCount, chatCount, onPasswordChanged, onSignOut }) {
    // ============================================================
    // STATE
    // ============================================================
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    // ============================================================
    // CHANGE PASSWORD
    // ============================================================
    const handleSubmit = async (event) => {
        event.preventDefault();
        setError("");

        if (newPassword !== confirmPassword) {
            setError("The new passwords do not match.");
            return;
        }

        setLoading(true);

        try {
            await changePassword({ currentPassword, newPassword });
            // The backend revokes every refresh token, so sign in again.
            onPasswordChanged();
        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <div className="account-grid">
            {/* ============================================================
                PROFILE
                ============================================================ */}
            <div className="panel tool-panel">
                <h2>Profile</h2>
                <p className="muted">Your account details.</p>

                <div className="profile-card">
                    <div className="avatar avatar-large">
                        {(user?.name || "?").charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <div className="profile-name">{user?.name}</div>
                        <div className="profile-caption">{user?.email}</div>
                    </div>
                </div>

                <div className="details-stats details-stats-compact">
                    <div>
                        <span>Documents</span>
                        <strong>{documentCount}</strong>
                    </div>
                    <div>
                        <span>Chat sessions</span>
                        <strong>{chatCount}</strong>
                    </div>
                </div>

                <button className="button sign-out-button" onClick={onSignOut}>
                    <Icon name="logout" /> Sign out
                </button>
            </div>

            {/* ============================================================
                CHANGE PASSWORD FORM
                ============================================================ */}
            <div className="panel tool-panel">
                <h2>Change password</h2>
                <p className="muted">
                    You will be signed out on all devices after changing your password.
                </p>

                <form className="auth-form account-form" onSubmit={handleSubmit}>
                    <div className="field-group">
                        <label htmlFor="current-password">Current password</label>
                        <input
                            id="current-password"
                            type="password"
                            value={currentPassword}
                            onChange={(event) => setCurrentPassword(event.target.value)}
                            autoComplete="current-password"
                            required
                        />
                    </div>

                    <div className="field-group">
                        <label htmlFor="new-password">New password</label>
                        <input
                            id="new-password"
                            type="password"
                            value={newPassword}
                            onChange={(event) => setNewPassword(event.target.value)}
                            autoComplete="new-password"
                            maxLength={128}
                            required
                        />
                        <ul className="password-rules">
                            {passwordRules.map((rule) => (
                                <li
                                    key={rule.label}
                                    className={rule.test(newPassword) ? "rule-met" : ""}
                                >
                                    {rule.label}
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="field-group">
                        <label htmlFor="confirm-password">Confirm new password</label>
                        <input
                            id="confirm-password"
                            type="password"
                            value={confirmPassword}
                            onChange={(event) => setConfirmPassword(event.target.value)}
                            autoComplete="new-password"
                            maxLength={128}
                            required
                        />
                    </div>

                    {error && (
                        <div className="form-alert error-alert" role="alert">
                            <strong>Unable to change password</strong>
                            <span>{error}</span>
                        </div>
                    )}

                    <button
                        className="submit-button"
                        type="submit"
                        disabled={loading || !passwordRules.every((rule) => rule.test(newPassword))}
                    >
                        {loading ? "Please wait..." : "Change password"}
                    </button>
                </form>
            </div>
        </div>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default AccountView;
