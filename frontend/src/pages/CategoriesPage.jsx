import { useState } from 'react'
import { api } from '../api.js'

// Add, rename and delete categories (Groceries, Rent, ...)
export default function CategoriesPage({ categories, reloadCategories, setError }) {
  const [name, setName] = useState('')           // what's in the name box
  const [editingId, setEditingId] = useState(null) // null = adding, a number = renaming that category

  async function save(event) {
    event.preventDefault()                         // stop the browser reloading the page
    setError('')
    try {
      if (editingId === null) {
        await api('/categories/', { method: 'POST', body: { name } })
      } else {
        await api(`/categories/${editingId}`, { method: 'PUT', body: { name } })
      }
      cancel()                                     // empty the form
      await reloadCategories()                     // every page shares this list, so reload it
    } catch (err) {
      setError(err.message)                        // e.g. "A category with this name already exists"
    }
  }

  async function remove(category) {
    setError('')
    try {
      await api(`/categories/${category.id}`, { method: 'DELETE' })
      if (category.id === editingId) cancel()
      await reloadCategories()
    } catch (err) {
      setError(err.message)                        // e.g. "This category still has transactions or budgets"
    }
  }

  function startEdit(category) {
    setEditingId(category.id)
    setName(category.name)
  }

  function cancel() {
    setEditingId(null)
    setName('')
  }

  return (
    <div className="row g-4">
      <div className="col-12 col-lg-4">
        <div className="card">
          <div className="card-header fw-semibold">{editingId === null ? 'Add a category' : 'Rename category'}</div>
          <form className="card-body d-grid gap-3" onSubmit={save}>
            <div>
              <label htmlFor="category-name" className="form-label">Name</label>
              <input
                id="category-name"
                className="form-control"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Groceries"
                required
                maxLength={50}                     // same limit as the API's schema
              />
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
          <div className="card-header fw-semibold">Categories</div>
          {categories.length === 0 ? (
            <div className="card-body text-body-secondary">No categories yet. Add your first one, for example Groceries.</div>
          ) : (
            <ul className="list-group list-group-flush">
              {categories.map((c) => (
                <li
                  key={c.id}
                  className={`list-group-item d-flex justify-content-between align-items-center ${c.id === editingId ? 'list-group-item-primary' : ''}`}
                >
                  <span>{c.name}</span>
                  <span className="d-flex gap-2">
                    <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => startEdit(c)}>Rename</button>
                    <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => remove(c)}>Delete</button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
