const WEIGHT_STOCK_UNITS = new Set(['кг', 'г', 'л', 'мл'])

function normalizeUnit(unit) {
  const raw = String(unit || '').trim().toLowerCase()
  if (!raw) return 'шт'
  if (raw === 'kg') return 'кг'
  if (raw === 'ml') return 'мл'
  if (raw === 'l') return 'л'
  if (raw === 'гр') return 'г'
  if (raw === 'pcs') return 'шт'
  return raw
}

function formatQuantity(value) {
  const num = Number(value)
  if (Number.isNaN(num) || num <= 0) return ''
  if (Number.isInteger(num)) return String(num)
  return num.toFixed(3).replace(/\.?0+$/, '')
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

  if (weight && !WEIGHT_STOCK_UNITS.has(unit)) {
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
  if (WEIGHT_STOCK_UNITS.has(unit)) return false

  return Number(product?.stock) > 0
}
