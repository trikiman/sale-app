# Phase 82 — CI Wiring + Lint Debt Start
**Milestone:** v1.25 Operator Visibility + Test Coverage
**Requirements:** TOOL-04 (CI wiring), TOOL-06 (spacing-scale rule)
**Started:** 2026-05-13

## Goal

Wire GitHub Actions CI for `npm run lint` + `npm run lint:css` + `pytest` so future PRs can't silently regress. Add the spacing-scale stylelint rule the v1.24 verifier suggested (using `declaration-property-value-allowed-list`, not custom plugin). Start the inline-style debt refactor but defer full completion (TOOL-05 all 46 violations) to v1.26 — refactoring 46 inline-style sites without regression is its own phase's scope.

## Scope adjustment from REQUIREMENTS.md

Original Phase 82 had TOOL-04 + TOOL-05 + TOOL-06 all in one phase. Reassessing after Phase 80/81 work:

- **TOOL-04 (CI wiring)** — in scope for Phase 82. Must be green end-to-end.
- **TOOL-05 (refactor all 46 inline-style violations + promote to ERROR)** — **deferred to v1.26**. 46 sites across App.jsx, HistoryPage.jsx, HistoryDetail.jsx, ProductDetail.jsx, CartPanel.jsx, main.jsx. Each requires judgment: extract to utility class vs. keep with disable+TODO. Doing this in a rush would cause regressions (the v1.23 Phase 75 layout-shift fix could regress if inline styles got moved wrong). Merits its own phase with per-file screenshots and careful verification.
- **TOOL-06 (spacing-scale rule)** — in scope for Phase 82 if using `declaration-property-value-allowed-list` approach that the verifier suggested. Pragmatic — ship the rule at WARN level, baseline any hits as debt entries.

Net Phase 82: CI + spacing-scale rule baselined. TOOL-05 moves to v1.26 scope.

## Implementation

### TOOL-04 — GitHub Actions workflow

`.github/workflows/lint-and-test.yml`:

```yaml
name: Lint & Test
on:
  pull_request:
  push:
    branches: [main]
jobs:
  lint:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: miniapp
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: miniapp/package-lock.json
      - run: npm ci
      - run: npm run lint
      - run: npm run lint:css

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install deps
        run: |
          pip install fastapi pytest httpx python-dotenv \
                      uvicorn aiohttp beautifulsoup4 sqlalchemy \
                      python-telegram-bot telegram-web-app lxml
      - name: Run backend tests
        run: python -m pytest backend/ -q
      - name: Run integration tests (Linux-only subset works)
        run: python -m pytest tests/test_vless_quarantine.py tests/test_collapse_replay.py tests/test_pool_state_io_race.py -q
```

**Note:** lint job passes today if pre-existing 23 eslint errors don't block merges. Decision: eslint errors are pre-existing baseline, not introduced by v1.25. Leaving `npm run lint` without `--max-warnings 0` means the new `react/forbid-dom-props` warnings are informational. The 23 errors will fail CI — they need fixing OR the workflow needs to tolerate them temporarily. Checking actual error list first.

### TOOL-06 — Spacing-scale stylelint rule

Add to `miniapp/.stylelintrc.json`:

```json
{
  "rules": {
    "declaration-property-value-allowed-list": {
      "/^(padding|margin|gap|row-gap|column-gap)(-(top|right|bottom|left))?$/": [
        "/^(0|auto|inherit|initial|unset|revert|none)$/",
        "/^var\\(--[\\w-]+\\)$/",
        "/^(0|4|8|12|16|24|32|48)(px)?$/",
        "/^(0|0\\.\\d+|\\d+(\\.\\d+)?)(em|rem|ch|%)$/",
        "/^calc\\(/"
      ]
    }
  }
}
```

At WARN severity initially. Run stylelint, count violations, decide:
- Small count (<10) → fix now, promote to ERROR
- Medium count (10-30) → baseline in `docs/style-guide-debt.md`, keep WARN, promote in v1.26
- Large count (>30) → defer the rule itself to v1.26 with a custom plugin design

### TOOL-05 — Minimal debt refactor (1-2 patterns)

Pick the 2 most-common inline-style patterns from the 46:
- `style={{ cursor: 'pointer' }}` on clickable divs → add `.clickable` utility class
- `style={{ gridColumn: '1/-1' }}` on full-width grid placeholders → add `.grid-row-full` utility class

Refactor just those 2 patterns. Don't touch the dynamic-style cases. Reduces 46 → ~30 with clear precedent for v1.26 bulk refactor.

## Non-Goals

- **Full inline-style refactor** — deferred to v1.26 (TOOL-05).
- **Pre-commit hooks via husky** — out of scope (CI is sufficient until team grows).
- **Spacing scale in CSS custom properties** — style guide v2 defines them; CSS migration is v1.26+ work.
- **Refactoring `style-guide-debt.md` drift** — deferred; add hook in v1.26 if CI alone proves insufficient.

## Files Touched

| File | Change |
|---|---|
| `.github/workflows/lint-and-test.yml` (new) | TOOL-04 CI workflow |
| `miniapp/.stylelintrc.json` | TOOL-06 spacing-scale rule addition |
| `miniapp/src/App.jsx` | TOOL-05 partial — extract 2 patterns to utility classes |
| `miniapp/src/index.css` | TOOL-05 partial — add `.clickable`, `.grid-row-full` |
| `docs/style-guide-debt.md` | Update counts + move TOOL-05 full refactor to v1.26 |

## Plan Order

Single commit per GSD discipline — all 3 changes interlock (CI needs stylelint rule decided + debt list accurate).

## Success Criteria

1. [ ] `.github/workflows/lint-and-test.yml` present + passes on push
2. [ ] CI job logs show `npm run lint:css` green
3. [ ] Pytest job green (backend/ + 3 new test files)
4. [ ] Spacing-scale rule added to `.stylelintrc.json`, violations baselined in `style-guide-debt.md` OR fixed if trivial
5. [ ] 2 common inline-style patterns extracted to utility classes; count drops from 46 → ≤35
6. [ ] No regression: all existing tests still pass
