"use client";

import { useCallback, useEffect, useState } from "react";

export function usePolling<T>(
  loader: () => Promise<T>,
  intervalMs = 2000,
): {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const result = await loader();
      setData(result);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load data",
      );
    } finally {
      setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
    const interval =
      intervalMs > 0
        ? window.setInterval(() => void reload(), intervalMs)
        : null;
    return () => {
      if (interval !== null) window.clearInterval(interval);
    };
  }, [intervalMs, reload]);

  return { data, loading, error, reload };
}
