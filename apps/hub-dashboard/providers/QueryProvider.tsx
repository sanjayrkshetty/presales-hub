"use client";
import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
} from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, type ReactNode } from "react";
import { isApiError } from "@/lib/errors";

function makeQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (isApiError(error) && error.isUnauthorized) {
          // Redirect to login on 401 — avoids routing dependency in this provider
          if (typeof window !== "undefined") window.location.href = "/login";
        }
        // Errors are surfaced through component-level isError / error — no global toast needed
        // for a component-isolated platform. Add a toast library here if desired later.
      },
    }),
    mutationCache: new MutationCache({
      onError: () => {
        // Mutation errors bubble to useMutation's onError — no global catch needed
      },
    }),
    defaultOptions: {
      queries: {
        staleTime:            30_000,
        gcTime:               5 * 60_000,
        refetchOnWindowFocus: true,
        retry: (failureCount, error) => {
          // Never retry client errors (4xx) — they won't fix themselves
          if (isApiError(error) && error.isClientError) return false;
          // Retry server errors up to 2 times
          return failureCount < 2;
        },
      },
      mutations: {
        retry: 0,  // mutations should never auto-retry — idempotency not guaranteed
      },
    },
  });
}

export function QueryProvider({ children }: { children: ReactNode }) {
  // useState ensures the QueryClient is created once per component lifetime
  const [client] = useState(makeQueryClient);
  return (
    <QueryClientProvider client={client}>
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
