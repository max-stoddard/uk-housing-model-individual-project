import { NavLink, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { ComparePage } from './pages/ComparePage';
import { RunModelPage } from './pages/RunModelPage';
import { ExperimentsPage } from './pages/ExperimentsPage';

export function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand-wrap">
          <p className="eyebrow">Max Stoddard BEng Individual Project</p>
          <h1>UK Housing Market ABM</h1>
        </div>
        <nav className="main-nav" aria-label="Main">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/compare">Model Parameters</NavLink>
          <NavLink to="/run-model">Run Model</NavLink>
          <NavLink to="/experiments">Experiments</NavLink>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/run-model" element={<RunModelPage />} />
          <Route path="/experiments" element={<ExperimentsPage />} />
        </Routes>
      </main>

      <footer className="app-footer">© 2026 Max Stoddard. All rights reserved.</footer>
    </div>
  );
}
