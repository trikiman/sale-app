import { useEffect, useState } from 'react'
import { formatQuantity, isWeightedUnit, normalizeUnit, parseQuantityInput } from './productMeta'

export default function CartQuantityControl({
  quantity,
  unit,
  compact = false,
  disabled = false,
  canIncrement = true,
  onDecrement,
  onIncrement,
  onCommitQuantity,
}) {
  const normalizedUnit = normalizeUnit(unit)
  const weighted = isWeightedUnit(normalizedUnit)
  const formattedQuantity = formatQuantity(quantity) || '0'
  const [draft, setDraft] = useState(formattedQuantity)

  useEffect(() => {
    setDraft(formattedQuantity)
  }, [formattedQuantity])

  const commitDraft = () => {
    if (disabled) {
      setDraft(formattedQuantity)
      return
    }

    const nextQuantity = parseQuantityInput(draft, normalizedUnit)
    if (nextQuantity == null) {
      setDraft(formattedQuantity)
      return
    }

    if (Number(nextQuantity) === Number(quantity)) {
      setDraft(formattedQuantity)
      return
    }

    onCommitQuantity?.(nextQuantity)
  }

  return (
    <div className={`cart-inline-qty ${compact ? 'compact' : 'detail'}`}>
      <button
        type="button"
        className="cart-inline-qty-btn"
        onClick={onDecrement}
        disabled={disabled}
        aria-label="Уменьшить количество"
      >
        −
      </button>

      <label className="cart-inline-qty-center">
        <input
          className="cart-inline-qty-input"
          value={draft}
          inputMode={weighted ? 'decimal' : 'numeric'}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={commitDraft}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.currentTarget.blur()
            } else if (event.key === 'Escape') {
              setDraft(formattedQuantity)
              event.currentTarget.blur()
            }
          }}
          aria-label={`Количество (${normalizedUnit})`}
        />
        <span className="cart-inline-qty-unit">{normalizedUnit}</span>
      </label>

      <button
        type="button"
        className="cart-inline-qty-btn"
        onClick={onIncrement}
        disabled={disabled || !canIncrement}
        aria-label="Увеличить количество"
      >
        +
      </button>
    </div>
  )
}
