// v1.26 Phase 83 Plan 83-01 smoke test — proves vitest + jsdom + jest-dom
// resolve correctly. Deleted at end of Phase 83 when real tests land.

import { describe, it, expect } from 'vitest'

describe('vitest harness', () => {
  it('runs a basic assertion', () => {
    expect(1 + 1).toBe(2)
  })

  it('has jsdom environment available', () => {
    expect(typeof window).toBe('object')
    expect(typeof document).toBe('object')
    expect(document.createElement('div')).toBeTruthy()
  })

  it('has jest-dom matchers available', () => {
    const el = document.createElement('div')
    el.textContent = 'hello'
    document.body.appendChild(el)
    expect(el).toBeInTheDocument()
    expect(el).toHaveTextContent('hello')
    document.body.removeChild(el)
  })
})
