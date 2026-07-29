import React from "react";
import { Button, ButtonProps } from "../ui/button";
import { Download } from "lucide-react";
import { cn } from "@/lib/utils";
import { useToast } from "../hooks/use-toast";
import { getPresignedUrl } from "@/lib/hey-api/client/sdk.gen";

export interface FileDownloadButtonProps extends Omit<ButtonProps, "onClick"> {
  fileID: string | null;
  downloadName: string;
  accessToken: string;
  children?: React.ReactNode; // Replace buttonText with children
}

const FileDownloadButton = React.forwardRef<
  HTMLButtonElement,
  FileDownloadButtonProps
>(
  (
    {
      fileID,
      downloadName,
      accessToken,
      children,
      className,
      variant = "outline",
      size,
      ...props
    },
    ref,
  ) => {
    const theToast = useToast();

    const handleDownload = async (e: React.MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      try {
        // If accessToken is "", show an error toast
        if (!accessToken || accessToken === "") {
          console.error("No access token provided");
          theToast.toast({
            title: "Error",
            description:
              "No authorization information found, aborting download",
            variant: "destructive",
          });
          return;
        }

        if (!fileID) {
          console.error("No file ID provided");
          theToast.toast({
            title: "Error",
            description: "No file ID provided, aborting download",
            variant: "destructive",
          });
          return;
        }

        const response = await getPresignedUrl({
          query: {
            filename: fileID,
          },
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
        });

        const presignedUrlData = response.data as { upload_url?: string; object_name?: string };
        const rawUrl = presignedUrlData?.upload_url;
        const objectName = presignedUrlData?.object_name;

        if (!rawUrl && !objectName) {
          throw new Error("Failed to get file URL");
        }

        // Clean query parameters to avoid signature mismatch on GET requests
        let cleanUrl = rawUrl ? rawUrl.split("?")[0] : "";
        if (!cleanUrl && objectName) {
          cleanUrl = `http://localhost:9000/uploads/${objectName}`;
        }

        // Route through /s3local proxy for same-origin fetch in browser
        if (typeof window !== "undefined") {
          cleanUrl = cleanUrl.replace(
            /^http:\/\/(localhost|127\.0\.0\.1):9000/,
            `${window.location.origin}/s3local`
          );
        }

        const fileResponse = await fetch(cleanUrl);
        if (!fileResponse.ok) {
          throw new Error(`Failed to fetch file (status ${fileResponse.status})`);
        }

        const blob = await fileResponse.blob();
        const blobUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = blobUrl;
        const fileName = downloadName.endsWith(".csv") ? downloadName : `${downloadName}.csv`;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(blobUrl);
      } catch (error) {
        console.error("Error downloading file:", error);
        theToast.toast({
          title: "Error",
          description: error instanceof Error ? error.message : "Failed to download file",
          variant: "destructive",
        });
      }
    };

    return (
      <Button
        ref={ref}
        type="button"
        variant={variant}
        size={size}
        className={cn("w-full", className)}
        onClick={handleDownload}
        {...props}
      >
        {children || (
          <>
            <Download className="h-4 w-4" />
            {`Download ${downloadName}`}
          </>
        )}
      </Button>
    );
  },
);

FileDownloadButton.displayName = "FileDownloadButton";

export default FileDownloadButton;
