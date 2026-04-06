const WEIGHT_STOCK_UNITS = new Set(['кг', 'г', 'л', 'мл'])

export function normalizeUnit(unit) {
  const raw = String(unit || '').trim().toLowerCase()
  if (!raw) return 'шт'
  if (raw === 'kg') return 'кг'
  if (raw === 'ml') return 'мл'
  if (raw === 'l') return 'л'
  if (raw === 'гр') return 'г'
  if (raw === 'pcs') return 'шт'
  return raw
}

export function isWeightedUnit(unit) {
  return WEIGHT_STOCK_UNITS.has(normalizeUnit(unit))
}

export function formatQuantity(value) {
  const num = Number(value)
  if (Number.isNaN(num) || num <= 0) return ''
  if (Number.isInteger(num)) return String(num)
  return num.toFixed(3).replace(/\.?0+$/, '')
}

export function parseQuantityInput(rawValue, unit) {
  const normalized = String(rawValue || '').trim().replace(',', '.')
  if (!normalized) return null

  const parsed = Number(normalized)
  if (!Number.isFinite(parsed) || parsed < 0) return null

  if (!isWeightedUnit(unit)) {
    return Number.isInteger(parsed) ? parsed : null
  }

  if (parsed === 0) return 0
  return Number(parsed.toFixed(3))
}

export function getCardMetaBadges(product) {
  const badges = []
  const unit = normalizeUnit(product?.unit)
  const quantity = formatQuantity(product?.stock)
  const weight = String(product?.weight || '').trim()

  if (quantity) {
    badges.push({
      kind: 'stock',
      text: `📦 ${quantity} ${unit}`,
    })
  }

  if (weight && !isWeightedUnit(unit)) {
    badges.push({
      kind: 'weight',
      text: weight,
    })
  }

  return badges
}

export function mergeResolvedWeights(products, resolvedWeights = {}) {
  return products.map((product) => {
    const existingWeight = String(product?.weight || '').trim()
    if (existingWeight) return product

    const resolvedWeight = String(resolvedWeights[product.id] || '').trim()
    if (!resolvedWeight) return product

    return {
      ...product,
      weight: resolvedWeight,
    }
  })
}

export function shouldFetchMissingWeight(product) {
  const weight = String(product?.weight || '').trim()
  if (weight) return false

  const unit = normalizeUnit(product?.unit)
  if (isWeightedUnit(unit)) return false

  return Number(product?.stock) > 0
}
