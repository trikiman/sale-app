# Phase 79 — Style Guide v2 Enforcement
**Milestone:** v1.24 Pool Self-Heal Hardening + Outage UX
**Requirements:** TOOL-02, TOOL-03
**Started:** 2026-05-13

## Goal

Automate the enforcement of two critical style guide v2 rules so future PRs can't silently regress:
- **TOOL-02:** stylelint rejects off-scale `padding`/`margin`/`gap` values (must be from `4/8/12/16/24/32/48` scale or use CSS vars)
- **TOOL-03:** eslint rejects inline `style={}` in JSX (must use CSS classes)

Pair with a baselined debt list in `docs/style-guide-debt.md` so existing violations are visible but don't block the CI until they're refactored in a future milestone.

## Scope

### TOOL-02: stylelint

Install `stylelint` + `stylelint-config-standard` + a custom rule for spacing scale.

`miniapp/.stylelintrc.json`:
```json
{
  "extends": ["stylelint-config-standard"],
  "rules": {
    "declaration-property-value-allowed-list": {
      "/^(padding|margin|gap|row-gap|column-gap|top|right|bottom|left)(-.*)?$/": [
        "/^(0|auto|inherit|initial|unset|revert)$/",
        "/^var\\(--.*\\)$/",
        "/^(-?)\\b(4|8|12|16|24|32|48)(px|%|em|rem|vh|vw)\\b/",
        "/calc\\(/"
      ]
    }
  },
  "ignoreFiles": ["dist/**/*"]
}
```

### TOOL-03: eslint inline-style ban

`eslint.config.js` rule addition:
```js
'react/forbid-dom-props': ['error', {
  forbid: [{
    propName: 'style',
    message: 'Use CSS classes instead. See docs/miniapp-ui-style-guide.md. Add eslint-disable-next-line with TODO(v1.25) if exception needed.'
  }]
}]
```

Requires `eslint-plugin-react` — not currently installed. Need to add it + wire rule.

### Baseline debt list

Document existing violations in `docs/style-guide-debt.md`. Don't fail CI on them — add `eslint-disable-next-line react/forbid-dom-props -- TODO(v1.25): refactor inline style` per offending line with structured grep-able `TODO(v1.25)` markers.

## Non-Goals

- **No refactor of existing violations** — v1.25 scope. Phase 79 only installs the guard rails.
- **No pre-commit hook via husky** — that's a separate tooling decision (would require husky install + team agreement). v1.24 just wires `npm run lint` to the new rules so CI can enforce if wired up later.
- **No stylelint auto-fix** — many existing usages are intentional (e.g. `padding: 0 16px 32px` where `0` is scale-compliant but `32px` is 32px from scale OK — but `padding: 0 4px 8px 10px` would flag `10px`). Safer to list violations and fix manually.
- **No SCSS/SASS migration** — stylelint works on raw CSS; no preprocessor needed.

## Files Touched

| File | Change |
|---|---|
| `miniapp/package.json` | Add stylelint + eslint-plugin-react devDependencies, `lint:css` script |
| `miniapp/.stylelintrc.json` (new) | Stylelint config with spacing scale allowlist |
| `miniapp/eslint.config.js` | Add `react/forbid-dom-props` rule |
| `docs/style-guide-debt.md` (new) | Baseline of existing violations with `TODO(v1.25)` markers |
| `scripts/verify_v1.24.sh` | Phase 79 smoke: `npm run lint && npm run lint:css` green |

## Plan Order

1. **79-01**: Install stylelint + config + baseline CSS debt
2. **79-02**: Install eslint-plugin-react + rule + baseline JSX debt
3. **79-03**: Verification — both linters green on baselined code

## Success Criteria

1. [ ] `miniapp/.stylelintrc.json` present; rejects off-scale spacing
2. [ ] `miniapp/eslint.config.js` rejects inline `style=` unless explicit disable
3. [ ] `docs/style-guide-debt.md` lists baselined violations with `TODO(v1.25)` tags
4. [ ] `npm run lint && npm run lint:css` green (baselined debt doesn't fail CI)
5. [ ] v1.23 + earlier regression green (CSS/JS lint is orthogonal to backend)
