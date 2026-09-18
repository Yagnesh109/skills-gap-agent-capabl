import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

function App() {
  const [selectedFile, setSelectedFile] = React.useState(null)
  const [isLoading, setIsLoading] = React.useState(false)
  const [message, setMessage] = React.useState('')
  const [result, setResult] = React.useState({})

  const handleFileChange = (event) => {
    const file = event.target.files[0]
    setSelectedFile(file || null)
    setMessage(file ? `Selected: ${file.name}` : '')
  }

  const handleSubmit = async () => {
    if (!selectedFile) {
      setMessage('Please choose a PDF, DOC, DOCX, or TXT resume first.')
      return
    }

    const filename = selectedFile.name.toLowerCase()
    if (!filename.endsWith('.pdf') && !filename.endsWith('.doc') && !filename.endsWith('.docx') && !filename.endsWith('.txt')) {
      setMessage('Invalid file type. Please upload a PDF, DOC, DOCX, or TXT file.')
      return
    }

    const formData = new FormData()
    formData.append('file', selectedFile)

    setIsLoading(true)
    setMessage('Uploading and parsing resume...')

    try {
      const response = await fetch('http://localhost:8000/api/profile/parse', {
        method: 'POST',
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'The profile parsing request failed.')
      }

      setResult(data)
      setMessage('Profile parsed successfully.')
    } catch (error) {
      setResult({ error: error.message })
      setMessage(error.message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="page-shell">
      <div className="card">
        <a className="back-link" href="/">← Back to Dashboard</a>
        <h1>Profile Parsing Agent</h1>
        <p className="subtitle">Upload a PDF, DOC, DOCX, or TXT resume and view the extracted structured profile.</p>

        <label className="upload-box">
          <span className="upload-label">Choose Resume</span>
          <input
            type="file"
            accept=".pdf,.doc,.docx,.txt,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={handleFileChange}
          />
        </label>

        <button onClick={handleSubmit} disabled={isLoading}>
          {isLoading ? 'Parsing...' : 'Parse Resume'}
        </button>

        <div className={`message ${message && message.includes('Please') || message.includes('Invalid') ? 'error' : ''}`}>
          {message}
        </div>

        <div className="result-panel">
          <h2>Structured JSON</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
