"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/hooks/useAuth";

interface Props {
  children: React.ReactNode;
  requiredPermission?: string;
}

export function RouteGuard({ children, requiredPermission }: Props) {
  const { isAuthenticated, isLoading, refreshSession, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated) {
      refreshSession().then((token) => {
        if (!token) router.replace("/login");
      });
    }
  }, [isAuthenticated, isLoading, refreshSession, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="text-[12px]" style={{ color: "var(--text-secondary)" }}>
          Loading…
        </span>
      </div>
    );
  }

  if (requiredPermission && !user?.permissions.includes(requiredPermission)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <span className="text-[12px]" style={{ color: "var(--danger)" }}>
          Access denied.
        </span>
      </div>
    );
  }

  return <>{children}</>;
}
