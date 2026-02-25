import { useCallback, useEffect, useMemo, useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import type { AuthStatusPayload } from '../shared/types';
import {
  fetchAuthStatus,
  logoutWriteAccess,
  setApiAuthToken
} from './lib/api';
import { ComparePage } from './pages/ComparePage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { ModelResultsPage } from './pages/ModelResultsPage';
import { RunExperimentsPage } from './pages/RunExperimentsPage';

const AUTH_TOKEN_STORAGE_KEY = 'dashboard.writeAuthToken';

const DEFAULT_AUTH_STATUS: AuthStatusPayload = {
  authEnabled: false,
  canWrite: true,
  authMisconfigured: false,
  modelRunsEnabled: false
};

function loadStoredAuthToken(): string | null {
  try {
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistAuthToken(token: string | null): void {
  try {
    if (token) {
      window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    } else {
      window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // ignore persistence failures
  }
}

export function App() {
  const isDevEnv = import.meta.env.DEV;
  const [authStatus, setAuthStatus] = useState<AuthStatusPayload>(DEFAULT_AUTH_STATUS);
  const [authLoaded, setAuthLoaded] = useState(false);
  const [authError, setAuthError] = useState('');

  const refreshAuthStatus = useCallback(async () => {
    try {
      const status = await fetchAuthStatus();
      setAuthStatus(status);
      if (status.authEnabled && !status.canWrite) {
        setApiAuthToken(null);
        persistAuthToken(null);
      }
      setAuthError('');
    } catch (error) {
      setAuthError((error as Error).message);
    } finally {
      setAuthLoaded(true);
    }
  }, []);

  useEffect(() => {
    const token = loadStoredAuthToken();
    setApiAuthToken(token);
    void refreshAuthStatus();
  }, [refreshAuthStatus]);

  const runExperimentsMisconfigured = authLoaded && authStatus.authMisconfigured;
  const runExperimentsLocked = authLoaded && authStatus.authEnabled && !authStatus.canWrite && !authStatus.authMisconfigured;
  const runExperimentsLink = useMemo(
    () => (runExperimentsMisconfigured ? '/model-results' : runExperimentsLocked ? '/login?next=/run-experiments' : '/run-experiments'),
    [runExperimentsLocked, runExperimentsMisconfigured]
  );

  const handleLoginSuccess = useCallback(
    async (token: string | null) => {
      setApiAuthToken(token);
      persistAuthToken(token);
      await refreshAuthStatus();
    },
    [refreshAuthStatus]
  );

  const handleLogout = useCallback(async () => {
    try {
      await logoutWriteAccess();
    } catch {
      // ignore logout API errors and clear token locally
    }
    setApiAuthToken(null);
    persistAuthToken(null);
    await refreshAuthStatus();
  }, [refreshAuthStatus]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-wrap">
          <p className="eyebrow">Max Stoddard BEng Individual Project</p>
          <h1 className="brand-title">
            <span>UK Housing Market ABM</span>
            {isDevEnv && <span className="env-pill-dev">Dev</span>}
          </h1>
        </div>
        <div className="header-nav-wrap">
          <nav className="main-nav" aria-label="Main">
            <NavLink to="/" end>
              Home
            </NavLink>
            <NavLink to="/compare">Calibration Versions</NavLink>
            <NavLink to={runExperimentsLink}>Run Experiments</NavLink>
            <NavLink to="/model-results">Model Results</NavLink>
            {authStatus.authEnabled && !authStatus.canWrite && !authStatus.authMisconfigured && (
              <NavLink className="main-nav-auth-control main-nav-auth-link" to="/login?next=/run-experiments">
                <span className="main-nav-auth-icon" aria-hidden="true">
                  <svg viewBox="0 0 20 20" role="img" aria-hidden="true">
                    <path
                      d="M10 2.5a3.75 3.75 0 1 0 0 7.5a3.75 3.75 0 0 0 0-7.5zm0 9c-3.44 0-6.25 1.98-6.25 4.42V17.5h12.5v-1.58c0-2.44-2.81-4.42-6.25-4.42z"
                      fill="currentColor"
                    />
                  </svg>
                </span>
                <span>Login</span>
              </NavLink>
            )}
            {authStatus.authEnabled && authStatus.canWrite && (
              <button type="button" className="main-nav-auth-control main-nav-auth-button" onClick={() => void handleLogout()}>
                <span className="main-nav-auth-icon" aria-hidden="true">
                  <svg viewBox="0 0 20 20" role="img" aria-hidden="true">
                    <path
                      d="M10 2.5a3.75 3.75 0 1 0 0 7.5a3.75 3.75 0 0 0 0-7.5zm0 9c-3.44 0-6.25 1.98-6.25 4.42V17.5h12.5v-1.58c0-2.44-2.81-4.42-6.25-4.42z"
                      fill="currentColor"
                    />
                  </svg>
                </span>
                <span>Logout</span>
              </button>
            )}
          </nav>
        </div>
      </header>

      <main className="app-main">
        {authError && <p className="error-banner">{authError}</p>}
        {authLoaded && authStatus.authMisconfigured && (
          <p className="error-banner">
            Write access is disabled: model runs are enabled but dashboard write credentials are not configured.
          </p>
        )}
        {!authLoaded ? (
          <p className="loading-banner">Checking access...</p>
        ) : (
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/model-results" element={<ModelResultsPage canWrite={authStatus.canWrite} />} />
            <Route
              path="/run-experiments"
              element={
                runExperimentsMisconfigured ? (
                  <Navigate to="/model-results" replace />
                ) : runExperimentsLocked ? (
                  <Navigate to="/login?next=/run-experiments" replace />
                ) : (
                  <RunExperimentsPage />
                )
              }
            />
            <Route
              path="/login"
              element={<LoginPage authStatus={authStatus} onLoginSuccess={handleLoginSuccess} />}
            />
            <Route path="/run-model" element={<Navigate to="/model-results" replace />} />
            <Route path="/experiments" element={<Navigate to="/run-experiments" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        )}
      </main>

      <footer className="app-footer">© 2026 Max Stoddard. All rights reserved.</footer>
    </div>
  );
}
