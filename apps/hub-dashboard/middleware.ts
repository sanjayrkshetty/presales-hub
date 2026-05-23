import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Paths that are always public — no auth check
const PUBLIC_PREFIXES = ["/login", "/_next/", "/favicon.ico", "/api/"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix))) {
    return NextResponse.next();
  }

  // The access token lives in-memory (Zustand), not in a cookie we can read here.
  // The refresh_token HttpOnly cookie is the server-visible proxy for "logged in".
  const hasSession = request.cookies.has("refresh_token");
  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
};
