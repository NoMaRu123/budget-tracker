import { useCallback, useEffect, useState } from 'react'
import NavBar from './components/NavBar.jsx'
import ErrorAlert from './components/ErrorAlert.jsx'
import OverviewPage from './pages/OverviewPage.jsx'
import TransactionsPage from './pages/TransactionsPage.jsx'
import BudgetsPage from './pages/BudgetsPage.jsx'
import CategoriesPage from './pages/CategoriesPage.jsx'
import { api } from './api.js'
import { currentMonth } from './dates.js'

// The tabs in the navbar: key -> label
const PAGES = { overview: 'Overview', transactions: 'Transactions', budgets: 'Budgets', categories: 'Categories' }

// "#budgets" in the address -> 'budgets'; anything unknown -> 'overview'
function pageFromUrl() {
  const key = window.location.hash.slice(1) // drop the '#'
  return key in PAGES ? key : 'overview'
}

// The whole app: holds what every page shares, and shows one page at a time
function App() {
  const [page, setPage] = useState(pageFromUrl)      // which tab is open (from the #... in the address)
  const [month, setMonth] = useState(currentMonth()) // the month every page shows, e.g. "2026-11"
  const [categories, setCategories] = useState([])   // used by every page (names, dropdowns)
  const [error, setError] = useState('')             // the red message at the top ('' = none)

  const [version, setVersion] = useState(0)          // add 1 to load the categories again

  useEffect(() => {                                   // runs at start, and after every reloadCategories()
    api('/categories/')
      .then(setCategories)
      .catch((err) => setError(err.message))
  }, [version])

  const reloadCategories = useCallback(() => setVersion((v) => v + 1), [])

  function goTo(key) {
    setError('')                // a new page starts without an old error
    setPage(key)
    window.location.hash = key  // the address becomes .../#budgets, so a refresh stays on this tab
  }

  // The same props for every page, passed with {...shared}
  const shared = { month, setMonth, categories, reloadCategories, setError, goTo }

  return (
    <>
      <NavBar pages={PAGES} page={page} onChange={goTo} />
      <main className="container py-4">
        <ErrorAlert message={error} onClose={() => setError('')} />
        {page === 'overview' && <OverviewPage {...shared} />}
        {page === 'transactions' && <TransactionsPage {...shared} />}
        {page === 'budgets' && <BudgetsPage {...shared} />}
        {page === 'categories' && <CategoriesPage {...shared} />}
      </main>
    </>
  )
}

export default App
