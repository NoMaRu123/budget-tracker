import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'

// A custom hook: loads one month's transactions and budgets, and loads them again when the month changes.
// Used by the Overview and Budgets pages, so the fetching code lives in one place.
export function useMonthData(month, setError) {
  const [data, setData] = useState({ transactions: [], budgets: [] })
  const [version, setVersion] = useState(0)            // add 1 to load again, e.g. after a save

  useEffect(() => {
    let current = true                                  // becomes false if the month changes mid-request
    Promise.all([                                       // ask for both at the same time
      api(`/transactions/?month=${month}`),
      api(`/budgets/?month=${month}`),
    ])
      .then(([transactions, budgets]) => { if (current) setData({ transactions, budgets }) })
      .catch((err) => setError(err.message))
    return () => { current = false }                    // cleanup: ignore a late answer for an old month
  }, [month, version, setError])

  const reload = useCallback(() => setVersion((v) => v + 1), [])

  return { ...data, reload }
}
