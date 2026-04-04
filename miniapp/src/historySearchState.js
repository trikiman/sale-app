export function getHistorySearchState(product) {
  if (product?.is_currently_on_sale) {
    return {
      kind: 'live',
      label: 'Сейчас на скидке',
      detail: 'Акция активна прямо сейчас',
    }
  }

  if ((product?.total_sale_count || 0) > 0) {
    return {
      kind: 'history',
      label: 'Была скидка',
      detail: 'Сейчас без активной акции, но история уже есть',
    }
  }

  return {
    kind: 'catalog',
    label: 'Есть в каталоге',
    detail: 'Скидок пока не было',
  }
}
