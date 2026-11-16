// A red Bootstrap alert with a close button. Shows nothing when there's no message.
export default function ErrorAlert({ message, onClose }) {
  if (!message) return null
  return (
    <div className="alert alert-danger d-flex justify-content-between align-items-start gap-3" role="alert">
      <span>{message}</span>
      <button type="button" className="btn-close" aria-label="Close" onClick={onClose}></button>
    </div>
  )
}
