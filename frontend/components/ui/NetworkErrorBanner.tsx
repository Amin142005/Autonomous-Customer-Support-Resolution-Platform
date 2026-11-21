"use client";

interface NetworkErrorBannerProps {
  message: string;
  onRetry?: () => void;
}

export function NetworkErrorBanner({
  message,
  onRetry,
}: NetworkErrorBannerProps) {
  return (
    <div
      role="alert"
      className="mb-4 flex items-center justify-between rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
    >
      <span>{message}</span>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="ml-4 rounded-md border border-red-300 px-3 py-1.5 font-medium hover:bg-red-100"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
