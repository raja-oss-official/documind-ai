// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useState } from "react";
import Icon from "./Icons.jsx";
import Modal from "./Modal.jsx";
import Select from "./Select.jsx";

// ============================================================
// ROLE LABELS
// ============================================================
const roleLabels = {
    viewer: "Can view",
    editor: "Can edit",
};

// ============================================================
// SHARE DIALOG (DOCUMENTS AND CHATS)
// ============================================================
// `roles` is ["viewer", "editor"] for documents and ["viewer"] for
// chats, which are shared read-only.
function ShareDialog({ title, subtitle, roles, loadShares, addShare, removeShare, onClose }) {
    // ============================================================
    // STATE
    // ============================================================
    const [shares, setShares] = useState(null);
    const [email, setEmail] = useState("");
    const [role, setRole] = useState(roles[0]);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");

    // ============================================================
    // LOAD CURRENT SHARES
    // ============================================================
    useEffect(() => {
        loadShares()
            .then(setShares)
            .catch((err) => {
                setError(err.message);
                setShares([]);
            });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ============================================================
    // ADD AND REMOVE
    // ============================================================
    const handleAdd = async (event) => {
        event.preventDefault();
        setBusy(true);
        setError("");

        try {
            const added = await addShare({ email: email.trim(), role });
            setShares((current) => [...(current || []).filter((item) => item.user_id !== added.user_id), added]);
            setEmail("");
        } catch (err) {
            setError(err.message);
        } finally {
            setBusy(false);
        }
    };

    const handleRemove = async (userId) => {
        setError("");

        try {
            await removeShare(userId);
            setShares((current) => current.filter((item) => item.user_id !== userId));
        } catch (err) {
            setError(err.message);
        }
    };

    // ============================================================
    // RENDER
    // ============================================================
    return (
        <Modal title={title} subtitle={subtitle} onClose={onClose}>
            <form className="share-form" onSubmit={handleAdd}>
                <input
                    className="text-input"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="Email of a DocuMind AI user"
                    required
                    autoFocus
                />
                {roles.length > 1 && (
                    <Select
                        ariaLabel="Permission"
                        value={role}
                        onChange={setRole}
                        options={roles.map((value) => ({ value, label: roleLabels[value] }))}
                    />
                )}
                <button className="button button-primary" type="submit" disabled={busy || !email.trim()}>
                    <Icon name="plus" /> {busy ? "Sharing..." : "Share"}
                </button>
            </form>

            {error && (
                <div className="notice notice-error" role="alert">
                    {error}
                </div>
            )}

            <div className="sub-heading share-heading">PEOPLE WITH ACCESS</div>

            {shares === null ? (
                <p className="muted">
                    <span className="spinner" /> Loading...
                </p>
            ) : shares.length === 0 ? (
                <p className="muted">Not shared with anyone yet.</p>
            ) : (
                <ul className="share-list">
                    {shares.map((share) => (
                        <li key={share.user_id}>
                            <span className="avatar">{(share.name || share.email || "?").charAt(0).toUpperCase()}</span>
                            <span className="share-person">
                                <strong>{share.name || share.email}</strong>
                                <small>{share.email}</small>
                            </span>
                            <span className="share-role">{roleLabels[share.role] || share.role}</span>
                            <button
                                className="cb-icon-button cb-icon-danger"
                                onClick={() => handleRemove(share.user_id)}
                                title="Stop sharing"
                                aria-label={`Stop sharing with ${share.name || share.email}`}
                            >
                                <Icon name="close" size={14} />
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </Modal>
    );
}

// ============================================================
// EXPORT
// ============================================================
export default ShareDialog;
