// Where the API lives: VITE_API_URL from the .env files; '' means "the same server that served this page"
export const API_URL = import.meta.env.VITE_API_URL ?? ''

// Send one request to the backend. Returns the JSON reply, or throws an Error with a readable message.
export async function api(path, { method = 'GET', body } = {}) {
  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,                                                         // GET, POST, PUT or DELETE
      headers: body ? { 'Content-Type': 'application/json' } : {},    // only say "JSON" when we send some
      body: body ? JSON.stringify(body) : undefined,                  // the data, as JSON text
    })
  } catch {
    // fetch only throws when there's no answer at all: server down, wrong address or CORS
    throw new Error(`Can't reach the API at ${API_URL || 'this server'}. Is the backend running?`)
  }

  const data = await response.json().catch(() => null) // a few error replies have no JSON body
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  return data
}

// Turn FastAPI's error reply into one sentence
function errorMessage(data, status) {
  if (typeof data?.detail === 'string') return data.detail // 404 and 409 send one sentence
  if (Array.isArray(data?.detail) && data.detail.length) {  // 422 sends a list of problems
    const first = data.detail[0]
    const field = first.loc?.[first.loc.length - 1]         // the field name is the last part of "loc"
    return field ? `${field}: ${first.msg}` : first.msg      // e.g. "amount_cents: Input should be greater than 0"
  }
  return `The server answered with status ${status}`
}
