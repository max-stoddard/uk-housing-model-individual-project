import { useEffect, useRef, useState } from 'react';
import { fetchExperimentJobLogs, isRetryableApiError } from '../../lib/api';

const MAX_LOG_LINES = 10_000;

export function useExperimentLogs(jobRef: string, enabled: boolean): { lines: string[]; error: string } {
  const [lines, setLines] = useState<string[]>([]);
  const [error, setError] = useState<string>('');
  const cursorRef = useRef<number>(0);

  useEffect(() => {
    setLines([]);
    setError('');
    cursorRef.current = 0;
  }, [jobRef]);

  useEffect(() => {
    if (!enabled || !jobRef) {
      return;
    }

    let cancelled = false;
    let done = false;

    const pollLogs = async () => {
      try {
        const payload = await fetchExperimentJobLogs(jobRef, cursorRef.current, 200);
        if (cancelled) {
          return;
        }

        cursorRef.current = payload.nextCursor;
        setLines((current) => {
          if (payload.truncated) {
            return payload.lines;
          }
          return [...current, ...payload.lines].slice(-MAX_LOG_LINES);
        });

        if (payload.done) {
          done = true;
        }
      } catch (fetchError) {
        if (!isRetryableApiError(fetchError)) {
          setError((fetchError as Error).message);
        }
      }
    };

    void pollLogs();
    const interval = window.setInterval(() => {
      if (!done) {
        void pollLogs();
      }
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [enabled, jobRef]);

  return { lines, error };
}
