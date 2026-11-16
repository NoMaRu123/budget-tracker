import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import MonthPicker from '../components/MonthPicker.jsx'
import { formatCents, eurosToCents, centsToEuros } from '../money.js'
import { today } from '../dates.js'

// An empty form. Amount is kept as typed text ("12.50") and only turned into cents when saving.
const emptyForm = () => ({ date: today(), description: '', amount: '', type: 'expense', category_id: '' })

// Add, edit, delete and filter transactions
export default function TransactionsPage({ month, setMonth, categories, setError, goTo }) {
  const [transactions, setTransactions] = useState([])
  const [categoryFilter, setCategoryFilter] = useState('')  // '' = all categories
  const [form, setForm] = useState(emptyForm)
  const [editingId, setEditingId] = useState(null)          // null = adding, a number = editing
  const names = Object.fromEntries(categories.map((c) => [c.id, c.name]))

  const [version, setVersion] = useState(0)                 // add 1 to load the list again

  // Load the list for the chosen month (and category, if one is picked). Runs again when a filter changes.
  useEffect(() => {
    let current = true                                       // false once the filters have changed again
    const query = new URLSearchParams({ month })             // builds "month=2026-11"
    if (categoryFilter) query.set('category_id', categoryFilter)
    api(`/transactions/?${query}`)
      .then((list) => { if (current) setTransactions(list) })
      .catch((err) => setError(err.message))
    return () => { current = false }                         // ignore a late answer for old filters
  }, [month, categoryFilter, version, setError])

  const load = useCallback(() => setVersion((v) => v + 1), [])

  // One change handler for every box: the box's name says which field to update
  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value })
  }

  async function save(event) {
    event.preventDefault()
    setError('')
    const body = {                                          // the shape the API's schema expects
      date: form.date,
      description: form.description,
      amount_cents: eurosToCents(form.amount),              // "12.50" -> 1250
      type: form.type,
      category_id: Number(form.category_id),
    }
    try {
      if (editingId === null) {
        await api('/transactions/', { method: 'POST', body })
      } else {
        await api(`/transactions/${editingId}`, { method: 'PUT', body })
      }
      cancel()
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(id) {
    setError('')
    try {
      await api(`/transactions/${id}`, { method: 'DELETE' })
      if (id === editingId) cancel()
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  function startEdit(t) {
    setEditingId(t.id)
    setForm({ ...t, amount: centsToEuros(t.amount_cents), category_id: String(t.category_id) }) // 1250 -> "12.50"
  }

  function cancel() {
    setEditingId(null)
    setForm(emptyForm())
  }

  // A transaction needs a category, so send the user there first if there are none
  if (categories.length === 0) {
    return (
      <div className="alert alert-info">
        Add a category before your first transaction.{' '}
        <button type="button" className="btn btn-link p-0 align-baseline" onClick={() => goTo('categories')}>Go to Categories</button>
      </div>
    )
  }

  return (
    <div className="row g-4">
      <div className="col-12 col-lg-4">
        <div className="card">
          <div className="card-header fw-semibold">{editingId === null ? 'Add a transaction' : 'Edit transaction'}</div>
          <form className="card-body d-grid gap-3" onSubmit={save}>
            <div>
              <label htmlFor="tx-type" className="form-label">Type</label>
              <select id="tx-type" name="type" className="form-select" value={form.type} onChange={update}>
                <option value="expense">Expense</option>
                <option value="income">Income</option>
              </select>
            </div>
            <div>
              <label htmlFor="tx-date" className="form-label">Date</label>
              <input id="tx-date" name="date" type="date" className="form-control" value={form.date} onChange={update} required />
            </div>
            <div>
              <label htmlFor="tx-description" className="form-label">Description</label>
              <input id="tx-description" name="description" className="form-control" value={form.description}
                onChange={update} placeholder="TESCO" required maxLength={200} />
            </div>
            <div>
              <label htmlFor="tx-amount" className="form-label">Amount (€)</label>
              <input id="tx-amount" name="amount" type="number" inputMode="decimal" step="0.01" min="0.01" max="1000000"
                className="form-control" value={form.amount} onChange={update} placeholder="12.50" required />
            </div>
            <div>
              <label htmlFor="tx-category" className="form-label">Category</label>
              <select id="tx-category" name="category_id" className="form-select" value={form.category_id} onChange={update} required>
                <option value="">Choose a category</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="d-flex gap-2">
              <button type="submit" className="btn btn-primary">{editingId === null ? 'Add' : 'Save'}</button>
              {editingId !== null && (
                <button type="button" className="btn btn-outline-secondary" onClick={cancel}>Cancel</button>
              )}
            </div>
          </form>
        </div>
      </div>

      <div className="col-12 col-lg-8">
        <div className="card">
          <div className="card-header d-flex flex-wrap justify-content-between align-items-center gap-2">
            <span className="fw-semibold">Transactions</span>
            <div className="d-flex flex-wrap gap-2">
              <MonthPicker month={month} setMonth={setMonth} id="tx-month" />
              <select className="form-select form-select-sm w-auto" aria-label="Filter by category"
                value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
                <option value="">All categories</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
          </div>
          {transactions.length === 0 ? (
            <div className="card-body text-body-secondary">No transactions for this month{categoryFilter ? ' and category' : ''}.</div>
          ) : (
            <div className="table-responsive">
              <table className="table table-hover align-middle mb-0">
                <thead>
                  <tr><th>Date</th><th>Description</th><th>Category</th><th className="text-end">Amount</th><th></th></tr>
                </thead>
                <tbody>
                  {transactions.map((t) => (
                    <tr key={t.id} className={t.id === editingId ? 'table-primary' : ''}>
                      <td className="text-nowrap">{t.date}</td>
                      <td>{t.description}</td>
                      <td>{names[t.category_id]}</td>
                      {/* income in green with +, expenses with - */}
                      <td className={`text-end money ${t.type === 'income' ? 'text-success' : ''}`}>
                        {t.type === 'income' ? '+' : '-'}{formatCents(t.amount_cents)}
                      </td>
                      <td className="text-end text-nowrap">
                        <button type="button" className="btn btn-sm btn-outline-secondary me-2" onClick={() => startEdit(t)}>Edit</button>
                        <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => remove(t.id)}>Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
