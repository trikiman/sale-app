# Legacy Code Archive

This directory holds implementations that have been superseded but are preserved
for rollback and historical reference. Nothing here is imported by the running
application. Subdirectories are named after the feature area they archive.

## Current Archives

### `proxy-socks5/` — Free SOCKS5 Proxy Pool (v1.0 – v1.14)

**Superseded by:** v1.15 VLESS+Reality pool via xray-core (see `vless/`).

**Reason:** The free SOCKS5 pool from `proxifly/free-proxy-list` degraded to
0% alive by 2026-04-22 (269/269 nodes dead across SOCKS5 and HTTP probes),
making cart-add and scraper runs unreliable.

**Rollback procedure** (single operation):

    git revert <commit-hash>

where `<commit-hash>` is the commit that introduced the shim (see
`git log -- proxy_manager.py` and find the commit with subject
`"chore(proxy): archive SOCKS5 implementation ..."`).

After the revert:

1. `proxy_manager.py` returns to the SOCKS5 implementation
2. `legacy/proxy-socks5/` is removed
3. `pytest` passes with the original SOCKS5 tests in force
4. The xray-core process, if running, can be stopped and uninstalled manually

**Rollback rehearsal** is performed as part of phase 56-05
(see `.planning/phases/56-vless-proxy-migration/56-05-SUMMARY.md`).

## Policy

- Files under `legacy/` are READ-ONLY in practice. Do not edit to "bring up
  to date" — if a bug exists in a legacy file, it stays there as the
  historical state. If the feature is needed again, revive the archive
  wholesale, do not cherry-pick.
- Legacy archives are deleted only when a milestone explicitly removes
  them. Absence of use is not a reason to delete — the whole point is
  preservation.
