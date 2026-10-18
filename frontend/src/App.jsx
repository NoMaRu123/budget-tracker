import { useState, useEffect } from 'react' // React tools: useState (remember data), useEffect (run code at load)
import './App.css' // load this component's styles

// Where the API lives: set in .env.development locally, empty (same origin) when built for AWS
const API_URL = import.meta.env.VITE_API_URL ?? '' // read the setting; if missing, use '' (same server)

function App() {
  const [items, setItems] = useState([])             // the list of items from the database, starts empty
  const [name, setName] = useState('')               // what's typed in the Name box
  const [description, setDescription] = useState('') // what's typed in the Description box
  const [error, setError] = useState('')             // error message to show in red ('' = no error)
  const [editingId, setEditingId] = useState(null)   // id of the item being edited (null = adding a new one)

  // Runs once, when the page first appears
  useEffect(() => {
    async function loadItems() {
      const response = await fetch(`${API_URL}/items/`) // GET /items/ from the backend
      const data = await response.json()                // turn the JSON reply into a JS list
      setItems(data)                                    // save it, React redraws the list
    }
    loadItems()
  }, []) // [] = only once, not on every redraw

  // Runs when the form is submitted (Add button or Enter key)
  async function createItem(event) {
    event.preventDefault() // stop the browser reloading the page (default form behaviour)
    setError('')           // clear any old error message

    const response = await fetch(`${API_URL}/items/`, { // send the new item to the backend
      method: 'POST',                                    // POST = create
      headers: { 'Content-Type': 'application/json' },   // tell the server the body is JSON
      body: JSON.stringify({ name, description }),       // the item, as JSON text
    })
    const data = await response.json() // the reply: the new item (with id) or an error

    if (!response.ok) { // not a 2xx status = something went wrong
      // 409/404 send detail as a string; 422 (validation) sends a list of problems
      setError(typeof data.detail === 'string' ? data.detail : data.detail[0].msg) // show the message
      return // stop here, don't add anything to the list
    }

    setItems([...items, data]) // new list = all old items + the new one, React redraws
    setName('')                // empty the Name box
    setDescription('')         // empty the Description box
  }

  // Runs when a Delete button is clicked
  async function deleteItem(id) {
    setError('') // clear any old error message

    const response = await fetch(`${API_URL}/items/${id}`, { // the URL says WHICH item, e.g. /items/3
      method: 'DELETE',                                      // DELETE = remove it
    })

    if (!response.ok) {                  // e.g. 404 if it was already deleted
      const data = await response.json() // read the error reply
      setError(data.detail)              // show it in red ("Item not found")
      return                             // stop, leave the list as it is
    }

    setItems(items.filter((item) => item.id !== id)) // new list = every item EXCEPT the deleted one
    if (id === editingId) cancelEdit()               // if that item was open in the form, close the form too
  }

  // Runs when an Edit button is clicked: copy that item into the form
  function startEdit(item) {
    setEditingId(item.id)                  // remember WHICH item we are editing
    setName(item.name)                     // put its name in the Name box
    setDescription(item.description ?? '') // put its description in the box ('' if it has none)
    setError('')                           // clear any old error message
  }

  // Runs when Cancel is clicked, and after a successful save: back to "add" mode
  function cancelEdit() {
    setEditingId(null) // null = not editing any more
    setName('')        // empty the Name box
    setDescription('') // empty the Description box
    setError('')       // clear any old error message
  }

  // Runs when the form is submitted WHILE editing
  async function updateItem(event) {
    event.preventDefault() // stop the browser reloading the page
    setError('')           // clear any old error message

    const response = await fetch(`${API_URL}/items/${editingId}`, { // the URL says WHICH item to change
      method: 'PUT',                                                // PUT = update
      headers: { 'Content-Type': 'application/json' },              // tell the server the body is JSON
      body: JSON.stringify({ name, description }),                  // the new values, as JSON text
    })
    const data = await response.json() // the reply: the updated item, or an error

    if (!response.ok) { // e.g. 409 duplicate name, 422 empty name, 404 already deleted
      setError(typeof data.detail === 'string' ? data.detail : data.detail[0].msg) // show the message
      return // stop here, stay in edit mode so the user can fix it
    }

    // Build a new list: for the item we edited use the updated version, keep every other item as it is
    setItems(items.map((item) => (item.id === editingId ? data : item)))
    cancelEdit() // leave edit mode and empty the boxes
  }

  return (
    <main>
      <h1>My CRUD App</h1>

      {/* The heading says which mode the form is in */}
      <h2>{editingId === null ? 'Add an item' : 'Edit item'}</h2>

      {/* One form, two jobs: not editing -> createItem, editing -> updateItem */}
      <form onSubmit={editingId === null ? createItem : updateItem}>
        <input
          placeholder="Name"                                // grey hint text when empty
          value={name}                                      // the box shows what `name` holds
          onChange={(event) => setName(event.target.value)} // every keystroke updates `name`
          required                                          // browser check: can't submit while empty
          maxLength={100}                                   // browser check: same limit as schemas.py
        />
        <input
          placeholder="Description"
          value={description}                                      // the box shows `description`
          onChange={(event) => setDescription(event.target.value)} // every keystroke updates it
          maxLength={500}                                          // browser check: same limit as schemas.py
        />
        {/* The button's label: 'Add' when not editing, 'Save' when editing */}
        <button type="submit">{editingId === null ? 'Add' : 'Save'}</button>
        {/* Cancel button: only drawn while editing. type="button" so it does NOT submit the form */}
        {editingId !== null && (
          <button type="button" onClick={cancelEdit}>Cancel</button>
        )}
      </form>

      {/* Only shows when there is an error message */}
      {error && <p className="error">{error}</p>}

      {/* If the list is empty show a message, otherwise show the table (if / else) */}
      {items.length === 0 ? (
        <p>No items yet.</p>
      ) : (
        <table>
          {/* The header row: column titles */}
          <thead>
            <tr>
              <th>Name</th>
              <th>Description</th>
              <th className="actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {/* For each item, make one table row (like a for loop) */}
            {items.map((item) => (
              <tr
                key={item.id}                                      // unique id so React can tell rows apart
                className={item.id === editingId ? 'editing' : ''} // highlight the row being edited
              >
                <td>{item.name}</td>
                <td>{item.description}</td>
                <td className="actions">
                  {/* Edit: copy THIS row's item into the form */}
                  <button onClick={() => startEdit(item)}>Edit</button>
                  {/* Delete: () => waits for the click, then deletes THIS row's item */}
                  <button className="danger" onClick={() => deleteItem(item.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}

export default App // let main.jsx import this component
