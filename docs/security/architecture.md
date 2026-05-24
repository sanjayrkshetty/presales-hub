# Security Architecture — Presales Hub

## Defense-in-Depth Layers

```mermaid
graph TB
    Internet[Internet] --> WAF
    subgraph Edge["Edge Security"]
        WAF[WAF / DDoS Protection\nCloudflare / AWS Shield]
        nginx[nginx\nRate limiting zones\nTLS 1.2/1.3 only\nHSTS 1 year]
    end

    subgraph API["API Security Layer"]
        MW[Middleware Stack\nCorrelationId · TenantContext\nTimeout · SizeLimit · SecurityHeaders]
        AUTH[Authentication\nJWT HMAC-SHA256\nBearer token]
        RBAC[Authorization\nRole-based access control\npresales_lead · sme · admin]
        RATE[Rate Limiting\nslowapi per-IP\n20 req/min login]
        LOCK[Account Lockout\n5 failed → 15 min]
    end

    subgraph Data["Data Security"]
        PG[(PostgreSQL\nTLS in transit\nEncrypted at rest)]
        RD[(Redis\nPassword auth\nIn-memory only)]
    end

    subgraph Headers["Security Headers"]
        FRAME[X-Frame-Options: DENY]
        SNIFF[X-Content-Type-Options: nosniff]
        CSP[Content-Security-Policy]
        XSS[X-XSS-Protection]
        HSTS[Strict-Transport-Security\nmax-age=31536000]
        REF[Referrer-Policy: strict-origin]
    end

    Internet --> WAF
    WAF --> nginx
    nginx --> MW
    MW --> AUTH
    AUTH --> RBAC
    RBAC --> RATE
    RATE --> LOCK
    LOCK --> Data
    MW --> Headers
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Hub API
    participant DB as PostgreSQL

    C->>A: POST /auth/login {email, password}
    A->>A: Rate limit check (20/min per IP)
    A->>DB: Fetch user by email
    DB-->>A: User record + failed_login_count
    A->>A: Check locked_until > now?
    Note over A: If locked: 429 Account locked
    A->>A: bcrypt.verify(password, hash)
    Note over A: On failure: increment failed_login_count<br/>If ≥5: set locked_until = now + 15 min
    A->>A: JWT sign {sub, tenant_id, roles, exp}
    A-->>C: {access_token, token_type, expires_in}
```

## Multi-Tenant Isolation

```mermaid
flowchart TB
    Request[HTTP Request] --> TC[TenantContextMiddleware]
    TC -->|extracts tenant_id\nfrom JWT or X-Tenant-ID| CTX[Request Context]
    CTX --> Filter[All DB queries\nfiltered by tenant_id]
    Filter --> PG[(PostgreSQL\nRow-level isolation)]

    subgraph Quotas["Quota Enforcement"]
        PG --> TQ[TenantQuota check\non every AI call]
        TQ -->|exceeded| Block[429 Quota Exceeded]
        TQ -->|ok| Allow[Process]
    end
```

## Secrets Management

```mermaid
flowchart LR
    subgraph Sources["Secret Sources"]
        SM[AWS Secrets Manager]
        K8S[Kubernetes Secrets]
        GHA[GitHub Encrypted Secrets]
    end

    subgraph Runtime
        ENV[Environment Variables\nDATABASE_URL\nJWT_SECRET_KEY\nPLATFORM_ADMIN_KEY\nANTHROPIC_API_KEY]
    end

    subgraph Validation
        BOOT[Startup Validator\ncore/config.py]
        BOOT -->|blocks startup if| RULES["❌ SQLite in production<br/>❌ DEBUG=true<br/>❌ dev-admin-key"]
    end

    Sources --> ENV
    ENV --> BOOT
```

## Threat Model Summary

| Threat | Mitigation |
|--------|-----------|
| Brute force login | 20 req/min rate limit + 5-attempt lockout (15 min) |
| SQL injection | SQLAlchemy ORM parameterized queries |
| XSS | CSP headers + X-XSS-Protection |
| Clickjacking | X-Frame-Options: DENY |
| MIME sniffing | X-Content-Type-Options: nosniff |
| Oversized payloads | RequestSizeLimitMiddleware (10 MB max) |
| Slow loris / timeout abuse | RequestTimeoutMiddleware (30s default) |
| Tenant data leakage | TenantContextMiddleware + row-level filtering |
| Insecure defaults | Startup validator rejects prod with dev defaults |
| API key exposure | Secrets Manager + never committed to git |
| AI prompt injection | Grounding score filter + safety_flags evaluation |
| AI provider outages | Circuit breaker with graceful degradation |
