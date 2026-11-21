"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface PollingOptions<T> {
  stopWhen?: (data: T) => boolean;
}

export function usePolling<T>(
  loader: () => Promise<T>,
  intervalMs = 2000,
  options: PollingOptions<T> = {},
): {
  data: T | null;
  loading: boolean;
  refreshing: boolean;
  pollingEnabled: boolean;
  error: string | null;
  reload: () => Promise<void>;
} {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollingEnabled, setPollingEnabled] = useState(intervalMs > 0);
  const inFlight = useRef(false);
  const { stopWhen } = options;

  const reload = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setRefreshing(true);

    try {
      const result = await loader();
      setData(result);
      setError(null);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Unable to load data",
      );
    } finally {
      inFlight.current = false;
      setRefreshing(false);
      setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    if (!pollingEnabled) return;
    void reload();
    const interval =
      intervalMs > 0
        ? window.setInterval(() => void reload(), intervalMs)
        : null;
    return () => {
      if (interval !== null) window.clearInterval(interval);
    };
  }, [intervalMs, reload, pollingEnabled]);

  useEffect(() => {
    if (stopWhen && data) {
      setPollingEnabled(!stopWhen(data));
    }
  }, [data, stopWhen]);

  return { data, loading, refreshing, pollingEnabled, error, reload };
}
