// The API stores money as whole cents (1250 = €12.50). These helpers convert for the screen.

const euro = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }) // Irish euro format

// 1250 -> "€12.50"
export function formatCents(cents) {
  return euro.format(cents / 100)
}

// "12.50" (what the user typed) -> 1250. Math.round removes float noise like 1249.9999.
export function eurosToCents(text) {
  return Math.round(Number(text) * 100)
}

// 1250 -> "12.50" (to put back into a form box when editing)
export function centsToEuros(cents) {
  return (cents / 100).toFixed(2)
}
