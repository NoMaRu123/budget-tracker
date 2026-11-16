import { useState } from 'react'
import { api } from '../api.js'
import MonthPicker from '../components/MonthPicker.jsx'
import BudgetBar from '../components/BudgetBar.jsx'
import { useMonthData } from '../useMonthData.js'
import { summarise } from '../summary.js'
import { formatCents, eurosToCents, centsToEuros } from '../money.js'
import { monthName } from '../dates.js'

// Set a monthly spending limit per category, and see how much of it is used
export default function BudgetsPage({ month, setMonth, categories, setError, goTo }) {
  const { transactions, budgets, reload } = useMonthData(month, setError)
  const { spent } = summarise(transactions)
  const [categoryId, setCategoryId] = useState('')
  const [limit, setLimit] = useState('')             // typed euros, e.g. "300"
  const [editingId, setEditingId] = useState(null)
  const names = Object.fromEntries(categories.map((c) => [c.id, c.name]))

  async function save(event) {
    event.preventDefault()
    setError('')
    const body = { month, limit_cents: eurosToCents(limit), category_id: Number(categoryId) } // the page's month
    try {
      if (editingId === null) {
        await api('/budgets/', { method: 'POST', body })
      } else {
        await api(`/budgets/${editingId}`, { method: 'PUT', body })
      }
      cancel()
      await reload()
    } catch (err) {
      setError(err.message)                        // e.g. "A budget for this category and month already exists"
    }
  }

  async function remove(id) {
    setError('')
    try {
      await api(`/budgets/${id}`, { method: 'DELETE' })
      if (id === editingId) cancel()
      await reload()
    } catch (err) {
      setError(err.message)
    }
  }

  function startEdit(b) {
    setEditingId(b.id)
    setCategoryId(String(b.category_id))
    setLimit(centsToEuros(b.limit_cents))
  }

  function cancel() {
    setEditingId(null)
    setCategoryId('')
    setLimit('')
  }

  if (categories.length === 0) {
    return (
      <div className="alert alert-info">
        Add a category before setting a budget.{' '}
        <button type="button" className="btn btn-link p-0 align-baseline" onClick={() => goTo('categories')}>Go to Categories</button>
      </div>
    )
  }

  return (
    <div className="row g-4">
      <div className="col-12 col-lg-4">
        <div className="card">
          <div className="card-header fw-semibold">
            {editingId === null ? 'Set a budget' : 'Edit budget'} for {monthName(month)}
          </div>
          <form className="card-body d-grid gap-3" onSubmit={save}>
            <div>
              <label htmlFor="budget-category" className="form-label">Category</label>
              <select id="budget-category" className="form-select" value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)} required>
                <option value="">Choose a category</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="budget-limit" className="form-label">Monthly limit (€)</label>
              <input id="budget-limit" type="number" inputMode="decimal" step="0.01" min="0.01" max="1000000"
                className="form-control" value={limit} onChange={(e) => setLimit(e.target.value)} placeholder="300" required />
            </div>
            <div className="d-flex gap-2">
              <button type="submit" className="btn btn-primary">{editingId === null ? 'Save budget' : 'Save'}</button>
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
            <span className="fw-semibold">Budgets</span>
            <MonthPicker month={month} setMonth={setMonth} id="budget-month" />
          </div>
          {budgets.length === 0 ? (
            <div className="card-body text-body-secondary">No budgets for {monthName(month)} yet.</div>
          ) : (
            <ul className="list-group list-group-flush">
              {budgets.map((b) => {
                const used = spent[b.category_id] ?? 0
                return (
                  <li key={b.id} className={`list-group-item ${b.id === editingId ? 'list-group-item-primary' : ''}`}>
                    <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-2">
                      <span>
                        <span className="fw-semibold">{names[b.category_id]}</span>
                        <span className="money text-body-secondary ms-2">{formatCents(used)} of {formatCents(b.limit_cents)}</span>
                      </span>
                      <span className="d-flex gap-2">
                        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => startEdit(b)}>Edit</button>
                        <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => remove(b.id)}>Delete</button>
                      </span>
                    </div>
                    <BudgetBar spent={used} limit={b.limit_cents} />
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
