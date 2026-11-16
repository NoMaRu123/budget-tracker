// Add up one month's transactions in the browser.
// Temporary: Phase C moves this into the analytics library, and the page will ask the API for it instead.
export function summarise(transactions) {
  let income = 0
  let expenses = 0
  const spent = {} // spending per category id, e.g. { 1: 4250, 3: 900 }

  for (const t of transactions) {
    if (t.type === 'income') {
      income += t.amount_cents
    } else {
      expenses += t.amount_cents
      spent[t.category_id] = (spent[t.category_id] ?? 0) + t.amount_cents // ?? 0: start at 0 the first time
    }
  }
  return { income, expenses, balance: income - expenses, spent }
}
