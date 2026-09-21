"use client";

import { useState, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { DatePickerWithRange } from "@/components/ui/date-range-picker";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Search, RefreshCw, CheckCircle2, XCircle, Clock, Activity } from "lucide-react";
import { DataTable } from "./data-table";
import { columns, LogEntry } from "./columns";
import { ContentLayout } from "@/components/admin-panel/content-layout";
import { getPipelines } from "@/lib/hey-api/client/sdk.gen";

interface Statistics {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  running_executions: number;
}

interface PipelineOption {
  id: string;
  name: string;
}

export default function LogStatistics() {
  const { data: session } = useSession();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [statistics, setStatistics] = useState<Statistics>({
    total_executions: 0,
    successful_executions: 0,
    failed_executions: 0,
    running_executions: 0,
  });
  const [pipelineOptions, setPipelineOptions] = useState<PipelineOption[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);

  // Load pipeline options
  useEffect(() => {
    const fetchPipelineOptions = async () => {
      if (!session?.user?.apiToken) return;
      try {
        const response = await getPipelines({
          headers: {
            Authorization: `Bearer ${session.user.apiToken}`,
            "Content-Type": "application/json",
          },
        });
        if (response.data && response.data.data) {
          const opts = response.data.data.map((p: any) => ({
            id: p._id,
            name: p.pipeline_name,
          }));
          setPipelineOptions(opts);
        }
      } catch (err) {
        console.error("Failed to fetch pipeline options:", err);
      }
    };
    fetchPipelineOptions();
  }, [session?.user?.apiToken]);

  // Fetch execution history and statistics
  const fetchExecutionData = useCallback(async () => {
    if (!session?.user?.apiToken) {
      setLoading(false);
      return;
    }

    try {
      setRefreshing(true);
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const queryParam = selectedPipeline !== "all" ? `?pipeline_id=${encodeURIComponent(selectedPipeline)}` : "";
      const res = await fetch(`${backendUrl}/pipelines/history${queryParam}`, {
        headers: {
          Authorization: `Bearer ${session.user.apiToken}`,
          "Content-Type": "application/json",
        },
      });

      if (!res.ok) {
        throw new Error(`Failed to fetch history: ${res.statusText}`);
      }

      const data = await res.json();
      if (data.statistics) {
        setStatistics(data.statistics);
      }
      if (data.executions) {
        setLogs(data.executions);
      }
    } catch (err) {
      console.error("Error loading pipeline execution history:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [session?.user?.apiToken, selectedPipeline]);

  useEffect(() => {
    fetchExecutionData();
  }, [fetchExecutionData]);

  // Filter logs by search query
  const filteredData = logs.filter((item) => {
    const query = searchQuery.toLowerCase();
    return (
      item.id.toLowerCase().includes(query) ||
      item.commands.toLowerCase().includes(query) ||
      item.user.toLowerCase().includes(query) ||
      item.status.toLowerCase().includes(query)
    );
  });

  return (
    <ContentLayout title="Pipeline Statistics">
      <div className="h-full flex flex-col space-y-6 p-4">
        {/* KPI Cards */}
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Runs</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{statistics.total_executions}</div>
              <p className="text-xs text-muted-foreground">All recorded executions</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Successful</CardTitle>
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-emerald-600">
                {statistics.successful_executions}
              </div>
              <p className="text-xs text-muted-foreground">Completed without errors</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Failed</CardTitle>
              <XCircle className="h-4 w-4 text-rose-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-rose-600">
                {statistics.failed_executions}
              </div>
              <p className="text-xs text-muted-foreground">Failed or error state</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Running</CardTitle>
              <Clock className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {statistics.running_executions}
              </div>
              <p className="text-xs text-muted-foreground">Active in background</p>
            </CardContent>
          </Card>
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search by execution ID, command, user, status..."
              className="pl-9 w-full"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-3">
            <div className="w-56">
              <Select value={selectedPipeline} onValueChange={setSelectedPipeline}>
                <SelectTrigger>
                  <SelectValue placeholder="All Pipelines" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Pipelines</SelectItem>
                  {pipelineOptions.map((pipe) => (
                    <SelectItem key={pipe.id} value={pipe.id}>
                      {pipe.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button
              variant="outline"
              size="icon"
              onClick={fetchExecutionData}
              disabled={refreshing}
              title="Refresh statistics"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Real Execution Logs Table */}
        <div className="space-y-2">
          <h3 className="text-base font-semibold">Execution History</h3>
          {loading ? (
            <div className="flex items-center justify-center h-48 border rounded-md">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-2"></div>
                <p className="text-sm text-muted-foreground">Loading real execution records...</p>
              </div>
            </div>
          ) : (
            <DataTable columns={columns} data={filteredData} />
          )}
        </div>
      </div>
    </ContentLayout>
  );
}
