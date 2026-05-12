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
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      // v1.24 TOOL-03: inline `style={}` forbidden per miniapp style guide v2.
      // Use CSS classes; if an exception is genuinely needed, add
      // `// eslint-disable-next-line react/forbid-dom-props -- TODO(v1.25): reason`
      // and link to docs/style-guide-debt.md.
      // Level is `warn` during v1.24 to baseline existing debt without
      // blocking CI; v1.25 polish phase should bump to `error` after debt
      // refactor is complete.
      'react/forbid-dom-props': ['warn', {
        forbid: [{
          propName: 'style',
          message: 'Use a CSS class. See docs/miniapp-ui-style-guide.md. If exception needed, disable with TODO(v1.25) comment.',
        }],
      }],
    },
  },
])
