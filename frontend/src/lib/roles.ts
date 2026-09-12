interface RoleCheckResponse {
  viewer: boolean;
  contributor: boolean;
  admin: boolean;
  role_name?: string;
}

interface RoleCheckRequest {
  path: string;
}

export async function checkRole(
  accessToken: string,
  pathname: string,
): Promise<RoleCheckResponse | null> {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim().replace(/\/$/, "");
    const url = `${backendUrl}/users/role-check`;
    console.log("[roles.ts] Role check request:", {
      url,
      pathname,
      hasToken: Boolean(accessToken),
    });
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        path: pathname,
      } as RoleCheckRequest),
    });

    if (!response.ok) {
      let errorBody: unknown = null;
      try {
        errorBody = await response.json();
      } catch {
        // ignore body parse error
      }
      console.error("[roles.ts] Error fetching roles", {
        status: response.status,
        statusText: response.statusText,
        url,
        pathname,
        errorBody,
      });
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data: RoleCheckResponse = await response.json();
    console.log("[roles.ts] Role check response:", data);

    if (!data) {
      console.error("[roles.ts] No roles found for user");
      return null;
    }

    return data;
  } catch (error) {
    console.error("[roles.ts] Error fetching roles:", error);
    throw error;
  }
}
