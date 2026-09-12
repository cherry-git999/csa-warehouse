import type { CreateClientConfig } from "./client/client.gen";

export const createClientConfig: CreateClientConfig = (config) => {
  if (!config) {
    throw new Error("Config is not provided.");
  }

  console.log("Creating custom client config with provided");
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL?.trim().replace(/\/$/, "");
  if (!backendUrl || backendUrl.length === 0) {
    throw new Error(
      "Environment variable NEXT_PUBLIC_BACKEND_URL is not set or is empty.",
    );
  }

  return {
    ...config,
    baseUrl: backendUrl,
    headers: {
      ...config.headers,
      Accept: "application/json",
    },
  };
};
