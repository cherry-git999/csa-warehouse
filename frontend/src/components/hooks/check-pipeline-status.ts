import { useEffect, useRef } from "react";

export type PipelineStatus = "running" | "completed" | "error" | "null";

export const usePipelineStatusCheck = (
  pipelineStatus: PipelineStatus,
  checkPipelineStatus: () => Promise<void>,
  pipelineId: string,
  execId: string | null,
) => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const pollCountRef = useRef<number>(0);

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    // Only poll if running and an execution ID is present
    if (pipelineStatus === "running" && execId) {
      pollCountRef.current = 0;
      // Immediate initial status check
      checkPipelineStatus();

      // Poll every 5 seconds, up to 30 attempts (150s max timeout) to avoid infinite polling
      intervalRef.current = setInterval(() => {
        pollCountRef.current += 1;
        if (pollCountRef.current >= 30) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          return;
        }
        checkPipelineStatus();
      }, 5000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [pipelineStatus, checkPipelineStatus, pipelineId, execId]);
};
