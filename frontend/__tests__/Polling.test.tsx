import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "@/lib/hooks";

describe("usePolling", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads data immediately and exposes polling state", async () => {
    const loader = vi.fn(async () => ({ status: "running" }));
    const { result } = renderHook(() => usePolling(loader, 1000));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual({ status: "running" });
    expect(result.current.error).toBeNull();
    expect(result.current.pollingEnabled).toBe(true);
  });

  it("stops polling for completed workflow data", async () => {
    const loader = vi.fn(async () => ({ status: "completed" }));
    const { result } = renderHook(() =>
      usePolling(loader, 1000, {
        stopWhen: (value) => value.status === "completed",
      }),
    );

    await waitFor(() => {
      expect(result.current.pollingEnabled).toBe(false);
    });

    expect(result.current.data).toEqual({ status: "completed" });
  });

  it("does not overlap an in-flight reload", async () => {
    let resolveLoad: ((value: { status: string }) => void) | null = null;
    const loader = vi.fn(
      () =>
        new Promise<{ status: string }>((resolve) => {
          resolveLoad = resolve;
        }),
    );

    const { result } = renderHook(() => usePolling(loader, 100));

    await waitFor(() => {
      expect(loader).toHaveBeenCalledTimes(1);
    });

    await result.current.reload();
    expect(loader).toHaveBeenCalledTimes(1);

    resolveLoad?.({ status: "running" });
  });
});
