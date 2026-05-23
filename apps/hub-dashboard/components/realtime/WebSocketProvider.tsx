"use client";
import { useEffect } from "react";
import { useWebSocketManager } from "@/lib/hooks/useWebSocket";

export function WebSocketProvider() {
  useWebSocketManager();
  return null;
}
