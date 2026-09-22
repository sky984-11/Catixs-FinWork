export function recordsCsv(rows) {
  const escape = (value) => {
    let text = String(value ?? '')
    if (/^[\s]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text)) text = `'${text}`
    return `"${text.replace(/"/g, '""')}"`
  }
  return '\uFEFF' + rows.map((row) => row.map(escape).join(',')).join('\r\n')
}
