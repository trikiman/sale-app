# Phase 21: Backend Proxy Unification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-01
**Phase:** 21-backend-proxy-unification
**Areas discussed:** Proxy strategy, Instance management, Error handling

---

## Proxy Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Direct first, proxy fallback | Try direct connection, use proxy only if direct fails | |
| Always proxy | All production VkusVill traffic goes through ProxyManager | ✓ |
| Hybrid per-endpoint | Some endpoints direct, some proxy | |

**User's choice:** Always proxy
**Notes:** "I may use [direct] for check something only, but not for regular work." Direct connections only for manual debugging.

---

## Instance Management

| Option | Description | Selected |
|--------|-------------|----------|
| Singleton | One shared ProxyManager instance for entire FastAPI app | ✓ (agent) |
| Per-request | Create fresh ProxyManager for each API call | |

**User's choice:** "I don't know what's better" — deferred to agent's discretion
**Notes:** Agent chose singleton to avoid re-loading cache on every request.

---

## Error Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Silent fallback | Return graceful error (source_unavailable), no monitoring | |
| Admin dashboard | Log failures + surface proxy health in admin panel | ✓ |

**User's choice:** Proxy dashboard — show failures in admin
**Notes:** User wants visibility into proxy health for monitoring.

## Agent's Discretion

- Singleton vs per-request ProxyManager instance (chose singleton)

## Deferred Ideas

None
