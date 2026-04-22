# Phase 56-05 — Summary

## Scope Delivered

- systemd unit for `xray-core` (`systemd/saleapp-xray.service`): hardened
  with `ProtectSystem=strict`, `NoNewPrivileges`, scoped `ReadWritePaths`,
  stdout/stderr appended to `bin/xray/logs/`, `Restart=always` with 5s
  backoff.
- scheduler unit (`systemd/saleapp-scheduler.service`): declares
  `Requires=saleapp-xray.service` and `After=saleapp-xray.service` so
  systemd starts and restarts the pair atomically.
- Deploy orchestrator (`scripts/deploy_v1_15.sh`): 8 steps, idempotent,
  exits non-zero on any failure, leaves `systemctl status` on screen for
  the operator.
- Live verifier (`scripts/verify_v1_15.sh`): 5 independent checks — xray
  health, RU egress, vkusvill reachability, scraper cycle, live cart
  add/remove. Step 5 skips cleanly if `PHPSESSID` is not exported.
- Cron safeguard (`scripts/xray_healthcheck.sh`): if `saleapp-xray` is
  active but port 10808 is not accepting, restarts the unit. Installed by
  the deploy script into the `ubuntu` user crontab at 5-minute cadence.
- Operator guide (`docs/PROXY_MIGRATION.md`): architecture, daily ops,
  troubleshooting, rollback procedure, xray upgrade procedure.
- Verification evidence (`56-VERIFICATION.md`): timestamped PASS/FAIL for
  every check that could be run on the dev box, plus a clearly-marked
  placeholder for the EC2 deploy + verify transcript.

## Dev-Box Verification Log (2026-04-22)

All 8 dev-side checks PASS. Evidence captured in `56-VERIFICATION.md`:

| Check | Result |
|-------|--------|
| A — xray binary installed and runnable | PASS |
| B — `scripts/bootstrap_xray.py --smoke-test` end-to-end | PASS (country=RU via 5 nodes) |
| C — `RUN_LIVE=1 test_live_vless_end_to_end` | PASS (28 RU nodes admitted) |
| D — full pytest (tests/ + backend/ + legacy/) | PASS (167 passed, 2 skipped) |
| E — ruff on vless/, tests/test_vless_*.py, proxy_manager.py | PASS |
| F — shim size + resolution | PASS (7 executable lines; resolves to VlessProxyManager) |
| G — `git log --follow` preserves SOCKS5 history | PASS (8 commits back to v1.0-era) |
| H — rollback rehearsal (`git revert cc70185` → pytest) | PASS (167 passed, 2 skipped) |

## Rollback Rehearsal

Performed 2026-04-22 on throwaway branch
`rehearse/v1.15-rollback-1776901542`. Reverted
`cc70185` (the 56-04 archive/shim commit) and re-ran `pytest tests/
backend/`. Result: **167 passed, 2 skipped**. The rehearsal confirms
that a single `git revert` restores the SOCKS5 code path without
touching any other plan's commits, meeting the atomicity contract in
56-04's acceptance criteria.

The rehearsal branch was deleted after verification. Local uncommitted
state: none.

## Deviations From Plan

1. **Archived SOCKS5 tests run under `legacy/proxy-socks5/tests/` rather
   than `tests/legacy/`.** The plan lists `tests/legacy/` as an optional
   location; putting the archived tests next to the archived
   implementation is tidier and a sibling `conftest.py` can use a
   relative path for the sys.path / sys.modules rebind.
2. **conftest.py uses `importlib.util.spec_from_file_location` instead
   of just `sys.path.insert`.** The plain sys.path approach loses to
   the production shim when the outer suite (e.g. `pytest tests/
   legacy/`) has already imported the shim. Rebinding via importlib
   is airtight regardless of invocation order; the archived tests'
   `import proxy_manager` reliably hits the SOCKS5 implementation.
3. **ruff.toml excludes `legacy/**`.** Archived files are read-only by
   policy (`legacy/README.md`); re-linting them would force edits that
   violate that policy. The exclusion is a single line in
   `[lint.per-file-ignores]`.
4. **EC2 rollout not executed in this session.** The execution
   environment did not have the `scraper-ec2-new` SSH key, so
   `deploy_v1_15.sh` + `verify_v1_15.sh` were not run against
   `ubuntu@13.60.174.46`. The scripts are in place and dev-verified.
   Operator action is required to complete the milestone.

## Milestone Closure

- Code + tests + deploy infra + docs + dev verification + rollback
  rehearsal: **COMPLETE** on `main`.
- EC2 live rollout + 5-check verification: **PENDING OPERATOR**. See
  "EC2 Rollout (pending operator action)" in `56-VERIFICATION.md` for
  the exact command + transcript format.

Once the operator runs the deploy/verify pair and appends the transcript
to `56-VERIFICATION.md`, the remaining ROADMAP Phase 56 success criteria
(points 2 and 3) flip to complete and v1.15 closes.
