// Dates in the formats the API expects, using the laptop's local time (not UTC)

const pad = (n) => String(n).padStart(2, '0') // 3 -> "03"

// "2026-11": the format of ?month= and of a budget's month
export function currentMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}` // getMonth() counts from 0, so add 1
}

// "2026-11-05": the format of a transaction's date
export function today() {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// "2026-11" -> "November 2026"
export function monthName(month) {
  const [year, m] = month.split('-').map(Number)
  return new Date(year, m - 1, 1).toLocaleDateString('en-IE', { month: 'long', year: 'numeric' })
}
