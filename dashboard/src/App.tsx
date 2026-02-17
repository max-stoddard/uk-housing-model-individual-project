import { useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { ComparePage } from './pages/ComparePage';
import { RunModelPage } from './pages/RunModelPage';
import { ExperimentsPage } from './pages/ExperimentsPage';

export function App() {
  const isDevEnv = import.meta.env.DEV;
  const [isProdPreviewEnabled, setIsProdPreviewEnabled] = useState<boolean>(false);
  const showDevFeatures = isDevEnv && !isProdPreviewEnabled;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-wrap">
          <p className="eyebrow">Max Stoddard BEng Individual Project</p>
          <h1 className="brand-title">
            <span>UK Housing Market ABM</span>
            {isDevEnv && <span className="env-pill-dev">Dev</span>}
            {isDevEnv && (
              <button
                type="button"
                className="env-toggle"
                onClick={() => setIsProdPreviewEnabled((current) => !current)}
                aria-pressed={isProdPreviewEnabled}
              >
                {isProdPreviewEnabled ? 'Show dev view' : 'Preview non-dev'}
              </button>
            )}
          </h1>
        </div>
        <nav className="main-nav" aria-label="Main">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/compare">Calibration Versions</NavLink>
          {showDevFeatures && <NavLink to="/run-model">Run Model</NavLink>}
          {showDevFeatures && <NavLink to="/experiments">Experiments</NavLink>}
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route
            path="/run-model"
            element={showDevFeatures ? <RunModelPage /> : <Navigate to="/" replace />}
          />
          <Route
            path="/experiments"
            element={showDevFeatures ? <ExperimentsPage /> : <Navigate to="/" replace />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="app-footer">© 2026 Max Stoddard. All rights reserved.</footer>
    </div>
  );
}
