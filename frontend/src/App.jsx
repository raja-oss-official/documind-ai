// ============================================================
// IMPORTS
// ============================================================
import { useEffect, useState } from "react";
import "./App.css";
import logoDark from "./assets/documind-logo-dark.png";
import logoLight from "./assets/documind-logo-light.png";
import Dashboard from "./components/Dashboard.jsx";
import Icon from "./components/Icons.jsx";
import Credits from "./components/Credits.jsx";
import {
  getCurrentUser,
  hasSession,
  loginUser,
  logoutUser,
  onSessionExpired,
  registerUser,
} from "./api.js";

// ============================================================
// APP: AUTHENTICATION AND SESSION
// ============================================================
function App() {
  // ============================================================
  // STATE
  // ============================================================
  const [page, setPage] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [user, setUser] = useState(null);
  const [checkingSession, setCheckingSession] = useState(hasSession);

  // ============================================================
  // RESTORE SAVED SESSION
  // ============================================================
  useEffect(() => {
    onSessionExpired(() => {
      setUser(null);
      setPage("login");
      setError("Your session has expired. Please sign in again.");
    });

    if (!hasSession()) {
      return;
    }

    getCurrentUser()
      .then(setUser)
      .catch(() => {})
      .finally(() => setCheckingSession(false));
  }, []);

  const isRegister = page === "register";

  // ============================================================
  // SIGN IN / REGISTER
  // ============================================================
  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);

    try {
      if (isRegister) {
        await registerUser({ name: name.trim(), email: email.trim(), password });
        setMessage("Account created successfully. You can now sign in.");
        setPage("login");
        setPassword("");
        return;
      }

      await loginUser({ email: email.trim(), password });
      setUser(await getCurrentUser());
      setPassword("");
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  // ============================================================
  // SWITCH BETWEEN SIGN IN AND REGISTER
  // ============================================================
  function switchPage(nextPage) {
    setPage(nextPage);
    setError("");
    setMessage("");
    setPassword("");
  }

  // ============================================================
  // SIGN OUT
  // ============================================================
  async function handleLogout(notice = "") {
    await logoutUser();
    setUser(null);
    setPage("login");
    setPassword("");
    setError("");
    setMessage(typeof notice === "string" ? notice : "");
  }

  // ============================================================
  // LOADING SCREEN
  // ============================================================
  if (checkingSession) {
    return (
      <main className="app-loading" role="status" aria-label="Loading your workspace">
        <div className="app-loading-inner">
          <div className="logo-lockup">
            <img className="brand-logo" src={logoLight} alt="DocuMind AI" />
            <span className="logo-slogan">Document Intelligence</span>
          </div>
          <div className="loading-bar" aria-hidden="true">
            <span />
          </div>
        </div>
      </main>
    );
  }

  // ============================================================
  // SIGNED-IN WORKSPACE
  // ============================================================
  if (user) {
    return <Dashboard user={user} onLogout={handleLogout} />;
  }

  return (
    <main className="auth-page">
      {/* ============================================================
          BRAND PANEL
          ============================================================ */}
      <section className="auth-brand-panel">
        <div className="auth-brand">
          <div className="logo-lockup logo-lockup-dark">
            <img className="brand-logo" src={logoDark} alt="DocuMind AI" />
            <span className="logo-slogan">Document Intelligence</span>
          </div>
        </div>

        <div className="brand-message">
          <h1>
            Your documents.
            <br />
            Your knowledge.
            <br />
            <span>One workspace.</span>
          </h1>

          <p>
            Bring your documents together, find information faster, and
            make your knowledge work for you.
          </p>
        </div>

        <div className="brand-footer">
          <Credits variant="dark" />
        </div>
      </section>

      {/* ============================================================
          SIGN-IN / REGISTER FORM
          ============================================================ */}
      <section className="auth-form-panel">
        <div className="auth-form-wrap">
          <div className="mobile-brand">
            <div className="logo-lockup">
              <img className="brand-logo" src={logoLight} alt="DocuMind AI" />
              <span className="logo-slogan">Document Intelligence</span>
            </div>
          </div>

          <div className="form-heading">
            <div className="form-eyebrow">
              {isRegister ? "GET STARTED" : "WELCOME BACK"}
            </div>

            <h2>
              {isRegister
                ? "Create your account"
                : "Sign in to your account"}
            </h2>

            <p>
              {isRegister
                ? "Create an account to set up your document workspace."
                : "Enter your credentials to access your workspace."}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {isRegister && (
              <div className="field-group">
                <label htmlFor="name">Full name</label>
                <input
                  id="name"
                  type="text"
                  placeholder="Enter your full name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="name"
                  required
                  maxLength={100}
                />
              </div>
            )}

            <div className="field-group">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </div>

            <div className="field-group">
              <div className="field-label-row">
                <label htmlFor="password">Password</label>
              </div>

              <div className="password-wrap">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder={
                    isRegister
                      ? "Create a secure password"
                      : "Enter your password"
                  }
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete={
                    isRegister ? "new-password" : "current-password"
                  }
                  required
                  minLength={isRegister ? 8 : undefined}
                />

                <button
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>

              {isRegister && (
                <p className="field-hint">
                  Use at least 8 characters with an uppercase letter, a
                  lowercase letter, a number, and a special character.
                </p>
              )}
            </div>

            {/* ============================================================
                FORM MESSAGES
                ============================================================ */}
            {error && (
              <div className="form-alert error-alert" role="alert">
                <strong>Unable to continue</strong>
                <span>{error}</span>
              </div>
            )}

            {message && (
              <div className="form-alert success-alert" role="status">
                {message}
              </div>
            )}

            <button className="submit-button" type="submit" disabled={loading}>
              {loading
                ? "Please wait..."
                : isRegister
                  ? "Create account"
                  : "Sign in"}
              {!loading && <Icon name="arrowRight" />}
            </button>
          </form>

          <div className="auth-switch">
            {isRegister
              ? "Already have an account?"
              : "New to DocuMind AI?"}{" "}
            <button
              type="button"
              onClick={() => switchPage(isRegister ? "login" : "register")}
            >
              {isRegister ? "Sign in" : "Create an account"}
            </button>
          </div>

          <div className="auth-note">
            <Icon name="lock" size={14} className="note-lock" />
            Your workspace is protected by account authentication.
          </div>
        </div>

        {/* ============================================================
            FORM FOOTER
            ============================================================ */}
        {/* Credits show here only on phones, where the brand panel is hidden. */}
        <footer className="form-footer">
          <Credits />
        </footer>
      </section>
    </main>
  );
}

// ============================================================
// EXPORT
// ============================================================
export default App;
