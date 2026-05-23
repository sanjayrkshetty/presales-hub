"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/useAuth";
import { ApiError } from "@/lib/errors";

export default function LoginPage() {
  const { login } = useAuth();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [error,    setError]    = useState<string | null>(null);
  const [loading,  setLoading]  = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Invalid email or password."
          : "Something went wrong. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-sm px-4">
      <div className="panel p-8 space-y-6">
        <div>
          <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            Presales Hub
          </h1>
          <p className="text-[12px] mt-1" style={{ color: "var(--text-secondary)" }}>
            Sign in to your account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-[11px] font-medium" style={{ color: "var(--text-secondary)" }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full px-3 py-2 text-[12px] rounded border bg-transparent outline-none transition-colors"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            />
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium" style={{ color: "var(--text-secondary)" }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full px-3 py-2 text-[12px] rounded border bg-transparent outline-none transition-colors"
              style={{ borderColor: "var(--border)", color: "var(--text-primary)" }}
            />
          </div>

          {error && (
            <p className="text-[11px]" style={{ color: "var(--danger)" }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 text-[12px] font-medium rounded transition-opacity disabled:opacity-50"
            style={{ background: "var(--accent)", color: "#fff" }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
