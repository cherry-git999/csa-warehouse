"use client";

import type { ColumnDef } from "@tanstack/react-table";

export type LogEntry = {
  id: string;
  commands: string;
  dateTime: string;
  user: string;
  status: string;
  duration: string;
};

export const columns: ColumnDef<LogEntry>[] = [
  {
    accessorKey: "id",
    header: "ID",
  },
  {
    accessorKey: "commands",
    header: "Commands",
  },
  {
    accessorKey: "dateTime",
    header: "Date/Time",
  },
  {
    accessorKey: "user",
    header: "User",
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => {
      const status = row.getValue("status") as string;
      const statusClass =
        status === "Completed"
          ? "text-emerald-600 dark:text-emerald-400 font-medium"
          : status === "Running"
          ? "text-blue-600 dark:text-blue-400 font-medium animate-pulse"
          : status === "Error"
          ? "text-red-600 dark:text-red-400 font-medium"
          : "";
      return <div className={statusClass}>{status}</div>;
    },
  },
  {
    accessorKey: "duration",
    header: "Duration",
  },
];
