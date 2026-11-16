// A month box. type="month" gives "2026-11", exactly the format the API's ?month= expects.
export default function MonthPicker({ month, setMonth, id = 'month' }) {
  return (
    <div className="d-flex align-items-center gap-2">
      <label htmlFor={id} className="form-label mb-0 text-body-secondary">Month</label>
      <input
        id={id}
        type="month"
        className="form-control form-control-sm w-auto"
        value={month}
        onChange={(e) => e.target.value && setMonth(e.target.value)} // ignore the "cleared" state
        pattern="\d{4}-\d{2}"                                         // for browsers without a month picker
        required
      />
    </div>
  )
}
