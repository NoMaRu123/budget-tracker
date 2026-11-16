import MonthPicker from '../components/MonthPicker.jsx'
import BudgetBar from '../components/BudgetBar.jsx'
import { useMonthData } from '../useMonthData.js'
import { summarise } from '../summary.js'
import { formatCents } from '../money.js'
import { monthName } from '../dates.js'

// The first page: this month's totals and how close each budget is to its limit
export default function OverviewPage({ month, setMonth, categories, setError, goTo }) {
  const { transactions, budgets } = useMonthData(month, setError)
  const { income, expenses, balance, spent } = summarise(transactions)
  const names = Object.fromEntries(categories.map((c) => [c.id, c.name])) // { 1: 'Groceries', ... }
  const overCount = budgets.filter((b) => (spent[b.category_id] ?? 0) > b.limit_cents).length

  return (
    <>
      <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
        <h1 className="h3 mb-0">{monthName(month)}</h1>
        <MonthPicker month={month} setMonth={setMonth} id="overview-month" />
      </div>

      {/* Three totals side by side; on a phone they stack */}
      <div className="row g-3 mb-4">
        <Total label="Income" cents={income} className="text-success" />
        <Total label="Expenses" cents={expenses} className="text-danger" />
        <Total label="Balance" cents={balance} className={balance < 0 ? 'text-danger' : ''} />
      </div>

      {overCount > 0 && (
        <div className="alert alert-warning" role="status">
          {overCount === 1 ? '1 budget is' : `${overCount} budgets are`} over the limit this month.
        </div>
      )}

      <div className="card">
        <div className="card-header d-flex justify-content-between align-items-center">
          <span className="fw-semibold">Budgets</span>
          <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => goTo('budgets')}>
            Manage budgets
          </button>
        </div>
        {budgets.length === 0 ? (
          <div className="card-body text-body-secondary">
            No budgets for {monthName(month)} yet. Set one on the Budgets page.
          </div>
        ) : (
          <ul className="list-group list-group-flush">
            {budgets.map((b) => {
              const used = spent[b.category_id] ?? 0
              const left = b.limit_cents - used
              return (
                <li className="list-group-item" key={b.id}>
                  <div className="d-flex justify-content-between flex-wrap gap-2 mb-1">
                    <span className="fw-semibold">{names[b.category_id] ?? 'Unknown category'}</span>
                    <span className="money">
                      {formatCents(used)} of {formatCents(b.limit_cents)}
                      <span className={left < 0 ? 'text-danger ms-2' : 'text-body-secondary ms-2'}>
                        {left < 0 ? `${formatCents(-left)} over` : `${formatCents(left)} left`}
                      </span>
                    </span>
                  </div>
                  <BudgetBar spent={used} limit={b.limit_cents} />
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </>
  )
}

// One total card. A small component used three times above.
function Total({ label, cents, className }) {
  return (
    <div className="col-12 col-md-4">
      <div className="card h-100">
        <div className="card-body">
          <div className="text-body-secondary small text-uppercase">{label}</div>
          <div className={`fs-3 fw-semibold money ${className}`}>{formatCents(cents)}</div>
        </div>
      </div>
    </div>
  )
}
