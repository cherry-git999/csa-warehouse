"use client";
import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { usePipelineStatusCheck } from "@/components/hooks/check-pipeline-status";
import { AlertCircle, CheckCircle, Loader2, Info } from "lucide-react";
import { runPipeline, getPipelineStatus } from "@/lib/hey-api/client/sdk.gen";
import { useSession } from "next-auth/react";

export interface LatestExecution {
  execution_id?: string | null;
  status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  error?: string | null;
}

export interface PipelineItem {
  _id: string;
  pipeline_name: string;
  is_enabled: boolean;
  pipeline_status: PipelineStatus;
  latest_execution?: LatestExecution | null;
}

export type PipelineStatus = "running" | "completed" | "error" | "null";

export interface RunPipelineRequest {
  pipeline_id: string;
  pipeline_name: string;
}

export interface RunPipelineResponse {
  status: string;
  execution_id: string;
  executed_at: string;
}

export function Pipeline({
  _id,
  pipeline_name,
  is_enabled,
  pipeline_status,
  latest_execution,
}: PipelineItem) {
  const [currentStatus, setCurrentStatus] =
    useState<PipelineStatus>(pipeline_status);
  const [currentExecId, setCurrentExecId] = useState<string | null>(
    latest_execution?.execution_id || null
  );
  const [errorMessage, setErrorMessage] = useState<string | null>(
    latest_execution?.error || null
  );
  const [startedAt, setStartedAt] = useState<string | null>(
    latest_execution?.created_at || null
  );
  const [completedAt, setCompletedAt] = useState<string | null>(
    latest_execution?.updated_at || null
  );
  const [consecutiveErrors, setConsecutiveErrors] = useState<number>(0);

  const { data: session } = useSession();

  const runPipelineRequest: RunPipelineRequest = {
    pipeline_id: _id,
    pipeline_name: pipeline_name,
  };

  const runPipelineFunction = async () => {
    try {
      setErrorMessage(null);
      setConsecutiveErrors(0);

      if (!session?.user?.apiToken) {
        setCurrentStatus("error");
        setErrorMessage("Authentication required: please log in to run pipelines.");
        return;
      }

      setCurrentStatus("running");
      const startTime = new Date().toISOString();
      setStartedAt(startTime);
      setCompletedAt(null);

      const response = await runPipeline({
        body: runPipelineRequest,
        headers: {
          Authorization: `Bearer ${session.user.apiToken}`,
          "Content-Type": "application/json",
        },
      });

      if (response.error) {
        const errDetail =
          (response.error as any)?.detail ||
          (response.error as any)?.message ||
          "Failed to start pipeline execution.";
        setCurrentStatus("error");
        setErrorMessage(typeof errDetail === "string" ? errDetail : JSON.stringify(errDetail));
        return;
      }

      if (response.data) {
        const responseData: RunPipelineResponse = response.data;
        setCurrentExecId(responseData.execution_id);
        setCurrentStatus(responseData.status as PipelineStatus);
        if (responseData.executed_at) {
          setStartedAt(responseData.executed_at);
        }
      } else {
        setCurrentStatus("error");
        setErrorMessage("No response data received from pipeline server.");
      }
    } catch (error: any) {
      console.error("Error starting pipeline:", error);
      setCurrentStatus("error");
      setErrorMessage(error?.message || "Network error starting pipeline.");
    }
  };

  const checkPipelineStatus = useCallback(async () => {
    if (!currentExecId) return;

    try {
      if (!session?.user?.apiToken) {
        setCurrentStatus("error");
        setErrorMessage("Authentication session expired while checking status.");
        return;
      }

      const response = await getPipelineStatus({
        query: {
          pipeline_id: _id,
          execution_id: currentExecId,
        },
        headers: {
          Authorization: `Bearer ${session.user.apiToken}`,
          "Content-Type": "application/json",
        },
      });

      if (response.error) {
        console.warn("Pipeline status check error:", response.error);
        setConsecutiveErrors((prev) => {
          const next = prev + 1;
          if (next >= 5) {
            setCurrentStatus("error");
            setErrorMessage("Pipeline status check failed after multiple attempts.");
          }
          return next;
        });
        return;
      }

      if (response.data) {
        const statusResult: PipelineStatus = response.data;
        setCurrentStatus(statusResult);
        setConsecutiveErrors(0);
        if (statusResult === "completed" || statusResult === "error") {
          setCompletedAt(new Date().toISOString());
        }
      }
    } catch (error: any) {
      console.warn("Network error checking pipeline status:", error);
      setConsecutiveErrors((prev) => {
        const next = prev + 1;
        if (next >= 5) {
          setCurrentStatus("error");
          setErrorMessage("Unable to connect to pipeline status service. Please verify backend.");
        }
        return next;
      });
    }
  }, [_id, currentExecId, session?.user?.apiToken]);

  usePipelineStatusCheck(
    currentStatus as PipelineStatus,
    checkPipelineStatus,
    _id,
    currentExecId,
  );

  return (
    <div className="border rounded-lg overflow-hidden bg-card text-card-foreground shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">Pipeline: {pipeline_name}</h2>
            {!is_enabled && (
              <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded">
                Disabled
              </span>
            )}
          </div>
          {currentExecId && (
            <div className="text-xs text-muted-foreground font-mono">
              Execution: {currentExecId}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={runPipelineFunction}
            disabled={currentStatus === "running"}
          >
            Run Pipeline
          </Button>

          {currentStatus === "running" && (
            <Button variant="secondary" size="sm" disabled>
              <div className="flex items-center gap-2">
                <Loader2 className="animate-spin h-4 w-4 text-blue-500" />
                <span>Running</span>
              </div>
            </Button>
          )}

          {currentStatus === "completed" && (
            <Button variant="secondary" size="sm" disabled>
              <div className="flex items-center gap-2">
                <CheckCircle className="text-green-500 h-4 w-4" />
                <span>Completed</span>
              </div>
            </Button>
          )}

          {currentStatus === "error" && (
            <Button variant="secondary" size="sm" disabled>
              <div className="flex items-center gap-2">
                <AlertCircle className="text-red-500 h-4 w-4" />
                <span>Error</span>
              </div>
            </Button>
          )}

          {currentStatus === "null" && (
            <Button variant="secondary" size="sm" disabled>
              Ready
            </Button>
          )}
        </div>
      </div>

      {(startedAt || errorMessage) && (
        <div className="px-4 pb-3 pt-0 border-t bg-muted/20 text-xs text-muted-foreground flex flex-col gap-1">
          {startedAt && (
            <div className="flex items-center gap-4 mt-2">
              <span>Started: {new Date(startedAt).toLocaleString()}</span>
              {completedAt && (
                <span>Completed: {new Date(completedAt).toLocaleString()}</span>
              )}
            </div>
          )}
          {errorMessage && (
            <div className="flex items-center gap-1.5 text-destructive mt-1">
              <AlertCircle className="h-3.5 w-3.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
