"use client";
import { Input } from "@/components/ui/input";
import { Search } from "lucide-react";
import { ContentLayout } from "@/components/admin-panel/content-layout";
import { useState, useEffect } from "react";
import { Pipeline } from "./pipe-item";
import { getPipelines } from "@/lib/hey-api/client/sdk.gen";
import { useSession } from "next-auth/react";

export interface PipelineItem {
  _id: string;
  pipeline_name: string;
  is_enabled: boolean;
  pipeline_status: PipelineStatus;
}

export type PipelineStatus = "running" | "completed" | "error" | "null";

export default function RunLogs() {
  const [pipelines, setPipelines] = useState<PipelineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const { data: session } = useSession();

  useEffect(() => {
    const fetchPipelines = async () => {
      if (!session?.user?.apiToken) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        // Call the API with authentication
        const response = await getPipelines({
          headers: {
            Authorization: `Bearer ${session.user.apiToken}`,
            "Content-Type": "application/json",
          },
        });

        if (response.data) {
          const responseData = response.data;
          const pipelines: PipelineItem[] = responseData.data;
          setPipelines(pipelines);
        }
      } catch (err) {
        console.error("Failed to fetch pipelines:", err);
      } finally {
        setLoading(false);
      }
    };

    fetchPipelines();
  }, [session?.user?.apiToken]);

  const filteredPipelines = pipelines.filter((p) =>
    p.pipeline_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <ContentLayout title="Pipelines">
      <div className="h-full flex flex-col p-6">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
              <p className="text-gray-600">Loading pipelines...</p>
            </div>
          </div>
        ) : (
          <>
            <div className="relative mb-8">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                type="search"
                placeholder="Search pipelines..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <h4 className="text-lg font-semibold mb-4">Technical Commands</h4>
            <div className="space-y-4">
              {filteredPipelines.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-500">
                    {pipelines.length === 0
                      ? "No pipelines found"
                      : "No pipelines match search query"}
                  </p>
                </div>
              ) : (
                filteredPipelines.map((pipeline) => (
                  <Pipeline
                    key={pipeline._id}
                    _id={pipeline._id}
                    pipeline_name={pipeline.pipeline_name}
                    is_enabled={pipeline.is_enabled}
                    pipeline_status={pipeline.pipeline_status}
                    latest_execution={(pipeline as any).latest_execution}
                  />
                ))
              )}
            </div>
          </>
        )}
      </div>
    </ContentLayout>
  );
}
