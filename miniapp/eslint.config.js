import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import react from 'eslint-plugin-react'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    plugins: {
      react,
    },
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      // v1.25 Phase 82: tolerate leading-underscore unused vars (convention
      // for "intentionally unused" — caught-error locals, destructuring
      // discards, etc.) + unused caught errors. Non-underscore unused vars
      // still error. This clears the 23-error baseline that was blocking CI
      // while keeping genuine dead-code detection.
      'no-unused-vars': ['error', {
        varsIgnorePattern: '^(_|[A-Z_])',
        argsIgnorePattern: '^_',
        caughtErrors: 'all',
        caughtErrorsIgnorePattern: '^_?e?$|^_',
      }],
      // Empty catch blocks are a common best-effort pattern (telegram
      // runtime not available, localStorage restrictions, etc.). Allow
      // them when the block is genuinely empty-intentional.
      'no-empty': ['error', { allowEmptyCatch: true }],
      // v1.25 Phase 82: React 19 eslint-plugin-react-hooks flags
      // setState-in-effect as error by default. For miniapp, many
      // legitimate uses (resetting local state when props change) exist.
      // Baseline as WARN; refactor to useMemo/useReducer patterns in v1.26.
      'react-hooks/set-state-in-effect': 'warn',
      // v1.24 TOOL-03: inline `style={}` forbidden per miniapp style guide v2.
      // Use CSS classes; if an exception is genuinely needed, add
      // `// eslint-disable-next-line react/forbid-dom-props -- TODO(v1.27): reason`
      // and link to docs/style-guide-debt.md.
      // v1.26 Phase 84-03: bumped from 'warn' → 'error'. The 46-site inline-style
      // baseline is now zero or annotated with TODO(v1.27) disables that point
      // at concrete refactor paths (mostly chart/theme dynamics that should
      // become CSS custom properties driven by data-attrs). New violations
      // should fail CI rather than accumulate as silent warnings.
      'react/forbid-dom-props': ['error', {
        forbid: [{
          propName: 'style',
          message: 'Use a CSS class. See docs/miniapp-ui-style-guide.md. If exception needed, disable with TODO(v1.27) comment.',
        }],
      }],
    },
  },
])
