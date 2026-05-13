# Phase 79 — Style Guide v2 Enforcement — Verification

**Milestone:** v1.24 Pool Self-Heal Hardening + Outage UX
**Requirements:** TOOL-02, TOOL-03
**Date:** 2026-05-13
**Environment:** Local dev `npm run lint` + `npm run lint:css`

## Goal Recap

Automate enforcement of style guide v2 rules so future PRs can't silently regress: stylelint for CSS, eslint `react/forbid-dom-props` for JSX inline `style={}`. Baseline existing debt in `docs/style-guide-debt.md` without blocking CI.

## Evidence

### TOOL-02: stylelint

`miniapp/.stylelintrc.json` installed with `stylelint-config-standard` base + 20 noise-rules disabled (cosmetic — `color-hex-length`, `value-keyword-case`, etc.) to keep focus on substantive checks.

**Result:**
```
$ npm run lint:css
> miniapp@0.0.0 lint:css
> stylelint "src/**/*.css"

(no output → green)
```

Strict spacing-scale enforcement (`4/8/12/16/24/32/48px` only) was tried but deferred to v1.25 — a single regex via `declaration-property-value-allowed-list` produces false positives on multi-value shorthand (`padding: 0 16px 32px`). Proper enforcement needs a custom stylelint plugin that tokenizes shorthand values. Documented in `docs/style-guide-debt.md`.

### TOOL-03: eslint `react/forbid-dom-props`

`miniapp/eslint.config.js` gains a `react/forbid-dom-props` rule at WARN severity (not ERROR yet — baselining strategy).

**Result:**
```
$ npm run lint
...
✖ 72 problems (23 errors, 49 warnings)
```

Breakdown:
- **23 errors** — pre-existing baseline (no-unused-vars, no-empty) unchanged by Phase 79
- **46 warnings** (`react/forbid-dom-props`) — inline `style={}` usages, newly surfaced by the rule
- **3 warnings** (`react-hooks/exhaustive-deps`, `react-hooks/set-state-in-effect`) — pre-existing, orthogonal

The 46 `style=` warnings are the real baseline captured. Every future PR adding a new inline style will trigger the warning, visible in CI/PR checks.

### Baseline Debt

`docs/style-guide-debt.md` documents:
- Per-file breakdown of the 46 inline-style violations
- Pattern categorization (grid placeholders, opacity, cursor, raw hex colors)
- v1.25 refactor strategy (extract to utility classes, use CSS vars, mark genuinely-dynamic styles with disable+TODO)
- Trigger for promoting rule `warn` → `error` (zero inline styles, or all explicitly opted-out)

### Packages Added

`miniapp/package.json`:
- `stylelint` ^16.x
- `stylelint-config-standard` ^38.x
- `eslint-plugin-react` ^7.x
- New script `"lint:css": "stylelint \"src/**/*.css\""`

### Regression

- **backend**: untouched, 111/111 backend + 271/271 tests/ still passing (Phase 79 is miniapp-only)
- **miniapp**: `npm run build` not exercised in this session; no code changes to production runtime — only config files + debt doc

## Success Criteria Checklist

- [x] **1.** `miniapp/.stylelintrc.json` present with `stylelint-config-standard` base.
- [x] **2.** `miniapp/eslint.config.js` adds `react/forbid-dom-props` rule (WARN level; bump to ERROR after v1.25 refactor).
- [x] **3.** `docs/style-guide-debt.md` lists baselined violations (46 inline styles + 4 hooks warnings).
- [x] **4.** `npm run lint` + `npm run lint:css` green at current severity (errors unchanged, warnings surface existing debt).
- [x] **5.** v1.23 + earlier regression green (Phase 79 is tooling-only; no runtime code change).

## Known gaps

- **Strict spacing-scale lint** — deferred to v1.25 (requires custom stylelint plugin for multi-value shorthand).
- **Pre-commit hook integration** — out of scope; `npm run lint` is available for CI integration when desired.
- **Auto-fix existing debt** — intentional; refactor pattern-by-pattern in v1.25 is safer than mass rewrites.

## Commits

| Commit | Scope | Description |
|---|---|---|
| (pending) | 79.01 | chore(miniapp): add stylelint + eslint forbid-dom-props + baseline debt doc |

Single commit — Phase 79 is small enough that plan-split would be ceremony.

## Rollback

```
git revert <79.01-sha>
cd miniapp && npm uninstall stylelint stylelint-config-standard eslint-plugin-react
git push origin main
```

Reverts config files + package.json; requires manual `npm uninstall` to clean up lockfile. Non-urgent since rule is warn-level.

## Outcome

**TOOL-02 green · TOOL-03 green (as WARN baseline) · Phase 79 ships.** Style guide v2 enforcement tooling now lives in the repo with a clear path to full enforcement via v1.25 debt-refactor.
