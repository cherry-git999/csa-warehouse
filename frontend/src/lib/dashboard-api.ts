/**
 * Dashboard API utilities
 * Functions to interact with the dashboard endpoints
 */

export interface DashboardInfo {
  name: string;
  path: string;
  mount_path: string;
  port: number;
  status: "registered" | "running" | "error";
}

export interface DashboardsResponse {
  dashboards: DashboardInfo[];
  count: number;
}

/**
 * Fetch all available dashboards from the backend
 */
export async function fetchDashboards(
  apiToken?: string
): Promise<DashboardsResponse> {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim().replace(/\/$/, "");
  if (!backendUrl) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");
  }

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  // Add auth header if token is provided
  if (apiToken) {
    headers.Authorization = `Bearer ${apiToken}`;
  }

  const response = await fetch(`${backendUrl}/dashboards`, {
    method: "GET",
    headers,
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch dashboards: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get the dashboard URL for embedding
 * Returns the backend URL that serves the dashboard in an iframe
 */
export function getDashboardUrl(mountPath: string): string {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim().replace(/\/$/, "");
  if (!backendUrl) {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not set");
  }

  // Use the mount_path directly from the API response
  // mount_path already includes /dashboard/{name}
  return `${backendUrl}${mountPath}`;
}

/**
 * Get the direct Streamlit URL (for direct access if needed)
 */
export function getDirectStreamlitUrl(port: number): string {
  return `http://localhost:${port}`;
}

