import { Link } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { fetchCatalog, fetchGitStats, fetchVersions } from '../lib/api';

export function HomePage() {
  const [versionsCount, setVersionsCount] = useState<number>(0);
  const [latestVersion, setLatestVersion] = useState<string>('...');
  const [cardsCount, setCardsCount] = useState<number>(0);
  const [filesChanged, setFilesChanged] = useState<number>(0);
  const [linesWritten, setLinesWritten] = useState<number>(0);
  const [commitCount, setCommitCount] = useState<number>(0);

  const formatCount = (value: number) => value.toLocaleString('en-GB');

  useEffect(() => {
    const load = async () => {
      const [versions, cards, gitStats] = await Promise.all([fetchVersions(), fetchCatalog(), fetchGitStats()]);
      setVersionsCount(versions.length);
      setLatestVersion(versions[versions.length - 1] ?? 'n/a');
      setCardsCount(cards.length);
      setFilesChanged(gitStats.filesChanged);
      setLinesWritten(gitStats.lineChanges);
      setCommitCount(gitStats.commitCount);
    };

    load().catch(() => {
      setVersionsCount(0);
      setLatestVersion('n/a');
      setCardsCount(0);
      setFilesChanged(0);
      setLinesWritten(0);
      setCommitCount(0);
    });
  }, []);

  return (
    <section className="home-layout">
      <div className="stats-grid fade-up-delay">
        <article>
          <p>Lines Written</p>
          <strong>{formatCount(linesWritten)}</strong>
        </article>
        <article>
          <p>Files Changed</p>
          <strong>{formatCount(filesChanged)}</strong>
        </article>
        <article>
          <p>Commits</p>
          <strong>{formatCount(commitCount)}</strong>
        </article>
        <article>
          <p>Snapshot Versions</p>
          <strong>{formatCount(versionsCount)}</strong>
        </article>
        <article>
          <p>Tracked Parameter Cards</p>
          <strong>{formatCount(cardsCount)}</strong>
        </article>
        <article>
          <p>Latest Snapshot</p>
          <strong>{latestVersion}</strong>
        </article>
      </div>

      <div className="hero-card fade-up">
        <p className="eyebrow">Main Individual Project Website</p>
        <h2>Visualize and track calibrated UK housing model parameters</h2>
        <p>
          This site is the main workspace for the individual project: it visualizes current model inputs, supports optional
          version comparison, and tracks calibration provenance from
          <code> input-data-versions/version-notes.json</code>.
        </p>
        <Link to="/compare" className="primary-button">
          Open Model Parameters
        </Link>
      </div>
    </section>
  );
}
