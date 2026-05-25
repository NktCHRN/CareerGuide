import { decodeJwt } from "jose";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Edge middleware: keeps the access-token cookie fresh and guards routes.
 *
 *  • Proactively refreshes the access token (using the refresh cookie) before a
 *    page renders, so Server Components always read a valid token. The new pair
 *    is written to both the forwarded request (this pass) and the response
 *    (browser persistence) — the documented Next.js cookie-rotation pattern.
 *  • Redirects unauthenticated users away from protected routes, and
 *    authenticated users away from the login/register pages.
 */

const ACCESS_COOKIE = "cg_access";
const REFRESH_COOKIE = "cg_refresh";
const GATEWAY_URL = (process.env.GATEWAY_URL ?? "http://localhost:8000").replace(/\/$/, "");
const COOKIE_SECURE = (process.env.COOKIE_SECURE ?? "false").toLowerCase() === "true";
const REFRESH_MAX_AGE = 60 * 60 * 24 * 30;

const PROTECTED_PREFIXES = ["/profile", "/recommendations", "/riasec", "/chats", "/admin"];
const AUTH_PAGES = ["/login", "/register"];

function isProtected(path: string): boolean {
  return PROTECTED_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`));
}

function tokenValid(token: string | undefined, skewSeconds = 30): boolean {
  if (!token) return false;
  try {
    const { exp } = decodeJwt(token);
    if (!exp) return true;
    return exp * 1000 > Date.now() + skewSeconds * 1000;
  } catch {
    return false;
  }
}

interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

async function tryRefresh(refresh: string): Promise<TokenPair | null> {
  try {
    const res = await fetch(`${GATEWAY_URL}/api/users/auth/refresh`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as TokenPair;
  } catch {
    return null;
  }
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: COOKIE_SECURE,
    path: "/",
    maxAge,
  };
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const access = req.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = req.cookies.get(REFRESH_COOKIE)?.value;

  let haveAccess = tokenValid(access);
  let refreshed: TokenPair | null = null;
  let cleared = false;

  if (!haveAccess && refresh) {
    refreshed = await tryRefresh(refresh);
    if (refreshed) {
      haveAccess = true;
      // Forward the new token to this request so the page renders authenticated.
      req.cookies.set(ACCESS_COOKIE, refreshed.access_token);
      req.cookies.set(REFRESH_COOKIE, refreshed.refresh_token);
    } else {
      cleared = true;
    }
  }

  // Unauthenticated access to a protected route → login.
  if (isProtected(pathname) && !haveAccess) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", pathname + (req.nextUrl.search || ""));
    const res = NextResponse.redirect(url);
    if (cleared) {
      res.cookies.delete(ACCESS_COOKIE);
      res.cookies.delete(REFRESH_COOKIE);
    }
    return res;
  }

  // Already-authenticated users skip the auth pages.
  if (AUTH_PAGES.includes(pathname) && haveAccess) {
    const url = req.nextUrl.clone();
    url.pathname = "/recommendations";
    url.search = "";
    const res = NextResponse.redirect(url);
    if (refreshed) {
      res.cookies.set(ACCESS_COOKIE, refreshed.access_token, cookieOptions(refreshed.expires_in));
      res.cookies.set(REFRESH_COOKIE, refreshed.refresh_token, cookieOptions(REFRESH_MAX_AGE));
    }
    return res;
  }

  const res = NextResponse.next({ request: { headers: req.headers } });
  if (refreshed) {
    res.cookies.set(ACCESS_COOKIE, refreshed.access_token, cookieOptions(refreshed.expires_in));
    res.cookies.set(REFRESH_COOKIE, refreshed.refresh_token, cookieOptions(REFRESH_MAX_AGE));
  }
  if (cleared) {
    res.cookies.delete(ACCESS_COOKIE);
    res.cookies.delete(REFRESH_COOKIE);
  }
  return res;
}

export const config = {
  // Run on everything except Next internals and static asset files.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt)$).*)",
  ],
};
