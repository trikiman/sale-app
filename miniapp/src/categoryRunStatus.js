function getRecentLines(lastOutput, maxLines = 4) {
  return String(lastOutput || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .slice(-maxLines)
}

export function buildCategoryRunView(status) {
  const lines = getRecentLines(status?.last_output)

  if (status?.running) {
    return {
      summary: lines.length > 0
        ? 'Идет определение категорий...'
        : 'Идет определение категорий. Обычно это занимает 1-3 минуты.',
      lines,
      isError: false,
    }
  }

  if (status?.exit_code != null && status.exit_code !== 0) {
    return {
      summary: 'Не удалось определить категории.',
      lines,
      isError: true,
    }
  }

  return {
    summary: '',
    lines,
    isError: false,
  }
}
