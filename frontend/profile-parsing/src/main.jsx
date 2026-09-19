import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

function App() {
  const [activeTab, setActiveTab] = React.useState('file')
  const [selectedFile, setSelectedFile] = React.useState(null)
  const [rawText, setRawText] = React.useState('')
  const [isLoading, setIsLoading] = React.useState(false)
  const [message, setMessage] = React.useState('')
  const [result, setResult] = React.useState({})

  const handleFileChange = (event) => {
    const file = event.target.files[0]
    setSelectedFile(file || null)
    setMessage(file ? `Selected: ${file.name}` : '')
  }

  const handleSubmit = async () => {
    if (activeTab === 'file') {
      if (!selectedFile) {
        setMessage('Please choose a PDF, DOC, DOCX, TXT, or Image resume file first.')
        return
      }

      const filename = selectedFile.name.toLowerCase()
      const allowedExts = ['.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff']
      if (!allowedExts.some((ext) => filename.endsWith(ext))) {
        setMessage('Invalid file type. Please upload a PDF, DOC, DOCX, TXT, or Image file.')
        return
      }

      const formData = new FormData()
      formData.append('file', selectedFile)

      setIsLoading(true)
      setMessage('Uploading and parsing resume file...')

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
    } else if (activeTab === 'text') {
      if (!rawText.trim()) {
        setMessage('Please enter or paste resume text first.')
        return
      }

      setIsLoading(true)
      setMessage('Parsing raw resume text...')

      try {
        const response = await fetch('http://localhost:8000/api/profile/parse-text', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ text: rawText }),
        })

        const data = await response.json()
        if (!response.ok) {
          throw new Error(data.detail || 'The profile text parsing request failed.')
        }

        setResult(data)
        setMessage('Profile parsed successfully from raw text.')
      } catch (error) {
        setResult({ error: error.message })
        setMessage(error.message)
      } finally {
        setIsLoading(false)
      }
    }
  }

  const isErrorMessage =
    message &&
    (message.includes('Please') ||
      message.includes('Invalid') ||
      message.includes('failed') ||
      message.includes('exceeded') ||
      message.includes('denied') ||
      message.includes('Could not'))

  return (
    <div className="page-shell">
      <div className="card">
        <a className="back-link" href="/">← Back to Dashboard</a>
        <h1>Profile Parsing Agent</h1>
        <p className="subtitle">
          Choose your preferred method to extract structured candidate profiles using AI & OCR.
        </p>

        <div className="tab-group">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'file' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('file')
              setMessage('')
            }}
          >
            Upload File
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'text' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('text')
              setMessage('')
            }}
          >
            Paste Raw Text
          </button>
        </div>

        {activeTab === 'file' && (
          <label className="upload-box">
            <span className="upload-label">Choose Resume (PDF, DOCX, TXT, PNG, JPG)</span>
            <input
              type="file"
              accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,image/*"
              onChange={handleFileChange}
            />
          </label>
        )}

        {activeTab === 'text' && (
          <div className="text-input-box">
            <label className="upload-label" htmlFor="raw-text">Paste Raw Resume Text</label>
            <textarea
              id="raw-text"
              className="raw-text-input"
              rows="10"
              placeholder="Paste complete resume text here (e.g., Jane Doe, Full Stack Developer, Skills: Python, React, PostgreSQL)..."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </div>
        )}

        <button className="submit-btn" onClick={handleSubmit} disabled={isLoading}>
          {isLoading
            ? 'Parsing...'
            : activeTab === 'file'
            ? 'Parse Resume File'
            : 'Parse Raw Text'}
        </button>

        <div className={`message ${isErrorMessage ? 'error' : ''}`}>{message}</div>

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


