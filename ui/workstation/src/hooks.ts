import { useCallback, useEffect, useState, type DependencyList } from 'react';

export function useRemote<T>(loader: (signal: AbortSignal) => Promise<T>, dependencies: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce(current => current + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    loader(controller.signal)
      .then(setData)
      .catch((caught: unknown) => {
        const failure = caught instanceof Error ? caught : new Error(String(caught));
        if (failure.name !== 'AbortError') setError(failure);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // Loader functions are stable module exports; caller controls explicit dependencies.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, ...dependencies]);

  return { data, error, loading, reload };
}
