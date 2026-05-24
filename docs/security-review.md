# Security Review — Phase 11

**Date:** 2026-05-24  
**Reviewer:** Phase 11 automated review + CLAUDE.md security guidelines  
**Scope:** Presales Hub API + Dashboard (Phase 10 baseline + Phase 11 hardening)

---

## Threat Model Summary

Based on the STRIDE methodology applied to the six attack surfaces below.

### Attack Surface 1: HTTP API (`/api/**`)

| Threat | Category | Mitigation | Status |
|--------|----------|-----------|--------|
| Unauthenticated endpoint access | Spoofing | JWT Bearer required on all `/api/**` routes | ✓ Implemented |
| Privilege escalation via tenant ID | Elevation | `TenantContextMiddleware` enforces tenant isolation; `X-Tenant-ID` validated against JWT claims | ✓ Implemented |
| Request body injection (SQLi) | Tampering | SQLAlchemy ORM with parameterized queries; no raw SQL | ✓ Implemented |
| Oversized body DoS | DoS | `RequestSizeLimitMiddleware` rejects >10 MB with 413 | ✓ Implemented |
| Request timeout abuse | DoS | `RequestTimeoutMiddleware` kills handlers after 30s | ✓ Implemented |
| Admin endpoint abuse | Elevation | `/api/admin/**` requires `X-Admin-Key` header; separate from user JWT | ✓ Implemented |
| SSRF via AI provider URLs | Tampering | Provider URLs hardcoded in config; user input not passed to HTTP client | ✓ Implemented |
| Sensitive data in logs | Info Disclosure | `SensitiveFilter` redacts password/token/secret/api_key/authorization fields | ✓ Phase 11 |

### Attack Surface 2: WebSocket (`/ws/**`)

| Threat | Category | Mitigation | Status |
|--------|----------|-----------|--------|
| Unauthenticated event subscription | Spoofing | JWT validated via `?token=` query param before `ws.accept()` | ✓ Phase 11 |
| WS broadcast data leakage | Info Disclosure | Events are tenant-scoped before broadcast | ✓ Implemented |
| WS connection flood | DoS | Event loop limits; NGINX upstream limits upstream connections | ⚠ Partial (no per-IP WS limit) |

### Attack Surface 3: Authentication (`/auth/**`)

| Threat | Category | Mitigation | Status |
|--------|----------|-----------|--------|
| Brute-force login | Spoofing | Rate limit: 20 req/min IP-level (`LoginRateLimiter`); account lockout after 5 failures (15 min) | ✓ Implemented |
| Credential stuffing | Spoofing | Same rate limit + lockout | ✓ Implemented |
| JWT forgery | Spoofing | HS256 signed with `SECRET_KEY`; `python-jose` + expiry enforced | ✓ Implemented |
| Refresh token theft | Spoofing | httpOnly cookie, SameSite=Lax, Secure=prod-only; hashed in DB, not stored raw | ✓ Implemented |
| Refresh token reuse | Repudiation | Tokens revoked on logout; `revoked_at` timestamp recorded | ✓ Implemented |
| No CSRF (form-based attack) | Tampering | Bearer token auth mitigates most CSRF; httpOnly refresh cookie susceptible to CSRF on `/auth/refresh` | ⚠ Known gap |
| No refresh token rotation | Repudiation | Stolen valid refresh token can be reused until expiry | ⚠ Known gap |

### Attack Surface 4: Admin Interface (`/api/admin/**`)

| Threat | Category | Mitigation | Status |
|--------|----------|-----------|--------|
| Admin key brute force | Spoofing | Static `X-Admin-Key` in environment variable; no rate limiting on admin specifically | ⚠ Partial |
| Admin actions not audited | Repudiation | `AuditLogMiddleware` logs all non-health requests including admin | ✓ Phase 11 |
| Admin key in logs | Info Disclosure | `SensitiveFilter` not applied to headers (only body fields) | ⚠ Partial |

### Attack Surface 5: AI Providers (Anthropic / OpenAI / Groq)

| Threat | Category | Mitigation | Status |
|--------|----------|-----------|--------|
| Provider failure cascades | DoS | Circuit breakers per provider (CLOSED/OPEN/HALF_OPEN), 5 failure threshold | ✓ Implemented |
| API key exposure | Info Disclosure | Keys in env vars; `SensitiveFilter` masks `api_key` in logs | ✓ Phase 11 |
| Prompt injection via user input | Tampering | User context passed to LLM as data, not as system prompt modification | ⚠ No explicit validation |
| Over-quota cost spike | DoS | AI governance: per-tenant token quota tracking; no hard enforcement yet | ⚠ Partial |

### Attack Surface 6: Frontend (Next.js Dashboard)

| Threat | Category | Mitigation | Status |
|--------|----------|-----------|--------|
| XSS via stored data | Tampering | React JSX auto-escaping; no dangerouslySetInnerHTML usage found | ✓ Implemented |
| Clickjacking | Tampering | `X-Frame-Options: DENY` + `frame-ancestors 'none'` in CSP | ✓ Phase 11 |
| Content sniffing | Info Disclosure | `X-Content-Type-Options: nosniff` | ✓ Implemented |
| MIME type attacks | Tampering | `nosniff` + strict Content-Type | ✓ Implemented |
| Mixed content | Info Disclosure | HSTS with `includeSubDomains; preload` in production | ✓ Phase 11 |
| Inline script injection | Tampering | CSP `script-src 'none'` on API responses | ✓ Phase 11 |
| Third-party script injection | Tampering | No third-party scripts loaded; analytics are self-hosted | ✓ Implemented |

---

## Phase 11 Security Changes Summary

| Change | File | Impact |
|--------|------|--------|
| CSP tightened: `default-src 'none'`, `script-src 'none'` | `middleware/security.py` | Eliminates inline script execution in API responses |
| `frame-ancestors 'none'` added | `middleware/security.py` | Belt-and-suspenders clickjacking prevention |
| `Permissions-Policy` header added | `middleware/security.py` | Disables camera/microphone/geolocation |
| HSTS upgraded to `preload` | `middleware/security.py` | Prevents protocol downgrade attacks |
| WS JWT validation on all 3 endpoints | `main.py` | Closes unauthenticated event subscription gap |
| CORS restricted to explicit methods/headers | `main.py` | Reduces attack surface for CORS-based exploits |
| Audit log middleware added | `middleware/audit.py` | Non-repudiation for all API actions |
| Sensitive field masking in logs | `telemetry/logging_config.py` | Prevents credential leakage in log aggregation |
| `LoginRateLimiter` replaces slowapi decorator | `middleware/rate_limit.py` | More reliable rate limiting; compatible with FastAPI 0.115.5 |

---

## Remaining Risks

| Risk | Severity | Remediation |
|------|----------|-------------|
| No CSRF protection on `/auth/refresh` | Medium | Add CSRF token to cookie-based refresh flow, or move to Bearer-only |
| No refresh token rotation | Medium | Rotate refresh token on each use; implement token family tracking |
| No formal penetration test | High | Engage external pen tester before first paying customer |
| Admin key not rate-limited | Low | Add `LoginRateLimiter` equivalent for `X-Admin-Key` validation |
| Prompt injection not validated | Medium | Add input sanitization layer before LLM prompt construction |
| No hard AI quota enforcement | Low | Implement Redis INCR counter to block over-quota requests |
| No SOC 2 audit evidence | Medium | Implement evidence collection hooks (audit logs → SIEM) |
| WS per-IP connection limit absent | Low | Add NGINX `limit_conn` for WebSocket upgrade requests |

---

## Security Headers (API)

```
Content-Security-Policy: default-src 'none'; connect-src 'self'; frame-ancestors 'none'
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
Permissions-Policy: camera=(), microphone=(), geolocation=()
```

---

## References

- OWASP Top 10 2021: A01 (Broken Access Control), A02 (Crypto Failures), A03 (Injection), A07 (Auth Failures)
- [docs/security/architecture.md](security/architecture.md) — detailed security architecture
- [middleware/security.py](../apps/hub-api/middleware/security.py) — header implementation
- [middleware/audit.py](../apps/hub-api/middleware/audit.py) — audit log middleware
