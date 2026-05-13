// v1.26 Phase 83 Plan 83-02 (TEST-03): extracted from App.jsx for testability.
// Cart step resolution — prefer the server-provided koef/step from the cart
// item, fall back to 0.01 for weighted units (кг, г, л, мл) and 1 for piece
// units. Pinned by miniapp/src/__tests__/cartStep.test.js.

import { isWeightedUnit } from './productMeta'

export function getCartStep(unit, cartItem) {
  const derived = Number(cartItem?.step || cartItem?.koef || 0)
  if (Number.isFinite(derived) && derived > 0) {
    return derived
  }

  return isWeightedUnit(unit) ? 0.01 : 1
}
