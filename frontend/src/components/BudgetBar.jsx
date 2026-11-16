// A progress bar: how much of a budget is spent. Green under 80%, amber from 80%, red when over.
export default function BudgetBar({ spent, limit }) {
  const percent = Math.round((spent / limit) * 100)
  const colour = percent > 100 ? 'bg-danger' : percent >= 80 ? 'bg-warning' : 'bg-success'
  const width = Math.min(percent, 100) // the bar stops at full, the label still says e.g. 130%

  return (
    <div
      className="progress"
      role="progressbar"
      aria-label="Share of the budget spent"
      aria-valuenow={width}
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div className={`progress-bar ${colour}`} style={{ width: `${width}%` }}>
        {percent}%
      </div>
    </div>
  )
}
