import type { ExperimentJobSummary } from '../../../shared/types';

interface ExperimentLogCardProps {
  selectedJob: ExperimentJobSummary | null;
  lines: string[];
}

export function ExperimentLogCard({ selectedJob, lines }: ExperimentLogCardProps) {
  return (
    <article className="results-card">
      <h3>Live Logs {selectedJob ? `(${selectedJob.title})` : ''}</h3>
      {selectedJob ? (
        <pre className="job-log-view">{lines.length === 0 ? 'No logs yet.' : lines.join('\n')}</pre>
      ) : (
        <p className="info-banner">Select a queue item to view logs.</p>
      )}
    </article>
  );
}
