// The dark bar at the top: app name plus one tab per page
export default function NavBar({ pages, page, onChange }) {
  return (
    <nav className="navbar navbar-expand bg-dark" data-bs-theme="dark">
      <div className="container flex-wrap gap-2">
        <span className="navbar-brand fw-semibold">Budget Tracker</span>
        <ul className="navbar-nav flex-wrap">
          {/* Object.entries turns { overview: 'Overview', ... } into [['overview', 'Overview'], ...] */}
          {Object.entries(pages).map(([key, label]) => (
            <li className="nav-item" key={key}>
              <button
                type="button"
                className={`nav-link ${page === key ? 'active' : ''}`} // Bootstrap highlights the active tab
                aria-current={page === key ? 'page' : undefined}      // tells screen readers which page is open
                onClick={() => onChange(key)}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
