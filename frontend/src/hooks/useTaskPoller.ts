import { useState, useEffect, useRef } from "react";
import DomainService, { TaskStatus } from "../services/domain.service";

interface UseTaskPollerOptions {
  onSuccess?: (result: Record<string, unknown>) => void;
  onError?: (error: string) => void;
  intervalMs?: number;
}

export function useTaskPoller(options: UseTaskPollerOptions = {}) {
  const { onSuccess, onError, intervalMs = 2000 } = options;
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startPolling = (id: string) => {
    setTaskId(id);
    setIsPolling(true);
  };

  const stopPolling = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setIsPolling(false);
  };

  useEffect(() => {
    if (!taskId || !isPolling) return;

    const poll = async () => {
      try {
        const result = await DomainService.getTaskStatus(taskId);
        setStatus(result);

        if (result.status === "SUCCESS") {
          stopPolling();
          onSuccess?.(result.result ?? {});
        } else if (result.status === "FAILURE") {
          stopPolling();
          onError?.(result.error ?? "Task failed");
        }
      } catch {
        // Network error — keep polling
      }
    };

    poll(); // Immediate first call
    intervalRef.current = setInterval(poll, intervalMs);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, isPolling]);

  return { status, isPolling, startPolling, stopPolling };
}
