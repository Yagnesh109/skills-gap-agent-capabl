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

  // Sequential Workflow States
  const [targetRole, setTargetRole] = React.useState('')
  const [matchedJobs, setMatchedJobs] = React.useState([])
  const [isMatchingLoading, setIsMatchingLoading] = React.useState(false)
  const [matchingMessage, setMatchingMessage] = React.useState('')

  const [gapAnalysis, setGapAnalysis] = React.useState(null)
  const [isGapLoading, setIsGapLoading] = React.useState(false)
  const [gapMessage, setGapMessage] = React.useState('')

  const handleFileChange = (event) => {
    const file = event.target.files[0]
    setSelectedFile(file || null)
    setMessage(file ? `Selected: ${file.name}` : '')
  }

  const handleSubmit = async () => {
    setMatchedJobs([])
    setGapAnalysis(null)
    setMatchingMessage('')
    setGapMessage('')

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
      setMessage('Uploading and parsing resume using AI & Vision...')

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
        if (data.profile?.experience?.[0]?.role) {
          setTargetRole(data.profile.experience[0].role)
        }
      } catch (error) {
        setResult({ error: error.message })
        setMessage(`Parsing Error: ${error.message}. (Ensure backend FastAPI is running on http://localhost:8000)`)
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
        if (data.profile?.experience?.[0]?.role) {
          setTargetRole(data.profile.experience[0].role)
        }
      } catch (error) {
        setResult({ error: error.message })
        setMessage(`Parsing Error: ${error.message}. (Ensure backend FastAPI is running on http://localhost:8000)`)
      } finally {
        setIsLoading(false)
      }
    }
  }

  // Step 2: Skill Matching Execution
  const handleSkillMatch = async () => {
    const candidateSkills = result.profile?.skills || []
    if (!candidateSkills.length) {
      setMatchingMessage('No candidate skills found in parsed profile.')
      return
    }

    setIsMatchingLoading(true)
    setMatchingMessage('Querying Skill Matching Agent backend...')

    try {
      const response = await fetch('http://localhost:8000/api/skill-match/match', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skills: candidateSkills,
          target_role: targetRole || '',
          location: result.profile?.personal_info?.location || '',
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Skill matching request failed.')
      }

      setMatchedJobs(data)
      setMatchingMessage(`Found and ranked ${data.length} matching job postings!`)
    } catch (err) {
      setMatchingMessage(`Skill Match Error: ${err.message}. Please check if backend server is running at http://localhost:8000`)
    } finally {
      setIsMatchingLoading(false)
    }
  }

  // Step 3: Gap Analysis Execution
  const handleGapAnalysis = async () => {
    const candidateSkills = result.profile?.skills || []
    if (!candidateSkills.length) {
      setGapMessage('No candidate skills available for gap analysis.')
      return
    }

    if (!matchedJobs.length) {
      setGapMessage('Please run Skill Match first to fetch job requirements.')
      return
    }

    setIsGapLoading(true)
    setGapMessage('Performing skill gap analysis and generating Gemini AI recommendations...')

    try {
      const jobsToAnalyze = matchedJobs.slice(0, 5).map((j, idx) => ({
        job_id: String(j.job_id || j.id || `job_${idx}`),
        job_title: j.title || j.job_title || targetRole || 'Software Engineer',
        required_skills: [...(j.matched_skills || []), ...(j.missing_skills || [])],
        match_score: j.match_score || j.overall_score || 0,
        matched_skills: j.matched_skills || [],
        missing_skills: j.missing_skills || [],
      }))

      const response = await fetch('http://localhost:8000/api/gap-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_profile: {
            skills: candidateSkills,
            location: result.profile?.personal_info?.location || '',
            education: result.profile?.education?.[0]?.degree || '',
          },
          jobs: jobsToAnalyze,
        }),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || 'Gap analysis request failed.')
      }

      setGapAnalysis(data)
      setGapMessage('Gap analysis & AI career guidance generated successfully!')
    } catch (err) {
      setGapMessage(`Gap Analysis Error: ${err.message}. Please check if backend server is running at http://localhost:8000`)
    } finally {
      setIsGapLoading(false)
    }
  }

  const handleReset = () => {
    setSelectedFile(null)
    setRawText('')
    setIsLoading(false)
    setMessage('')
    setResult({})

    setTargetRole('')
    setMatchedJobs([])
    setIsMatchingLoading(false)
    setMatchingMessage('')

    setGapAnalysis(null)
    setIsGapLoading(false)
    setGapMessage('')
    setActiveTab('file')

    const fileInput = document.querySelector('input[type="file"]')
    if (fileInput) {
      fileInput.value = ''
    }
  }

  const isErrorMessage =
    message &&
    (message.includes('Please') ||
      message.includes('Invalid') ||
      message.includes('failed') ||
      message.includes('exceeded') ||
      message.includes('Could not') ||
      message.includes('Error'))

  const hasParsedProfile = result.profile && result.success

  return (
    <div className="page-shell">
      <div className="card">
        <div className="header-row">
          <div>
            <h1>Career Intelligence & Profile Parsing Agent</h1>
            <p className="subtitle">
              Extract structured candidate profiles using AI & Vision, match skills against job postings, and perform automated Skill Gap Analysis.
            </p>
          </div>
          {hasParsedProfile && (
            <button className="analyze-more-btn" onClick={handleReset} title="Clear page & analyze another profile">
              🔄 Analyze More
            </button>
          )}
        </div>

        {/* Step 1: Profile Parsing Input */}
        <div className="tab-group">
          <button
            type="button"
            className={`tab-btn ${activeTab === 'file' ? 'active' : ''}`}
            onClick={() => {
              setActiveTab('file')
              setMessage('')
            }}
          >
            Upload Resume File
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
              rows="8"
              placeholder="Paste complete resume text here (e.g., Jane Doe, Full Stack Developer, Skills: Python, React, PostgreSQL)..."
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
          </div>
        )}

        <button className="submit-btn" onClick={handleSubmit} disabled={isLoading}>
          {isLoading ? 'Parsing Resume...' : activeTab === 'file' ? 'Parse Resume File' : 'Parse Raw Text'}
        </button>

        <div className={`message ${isErrorMessage ? 'error' : ''}`}>{message}</div>

        {/* Structured JSON Result */}
        {hasParsedProfile && (
          <div className="result-panel">
            <h2>Step 1 Result: Structured Candidate Profile</h2>
            <pre>{JSON.stringify(result.profile, null, 2)}</pre>
          </div>
        )}

        {/* Step 2: Skill Matching Action & Results */}
        {hasParsedProfile && (
          <div className="step-section">
            <div className="step-header">
              <h2>Step 2: Skill Matching Agent</h2>
              <p>Find matching job postings based on candidate's extracted skills.</p>
            </div>

            <div className="input-row">
              <input
                type="text"
                className="role-input"
                placeholder="Target Job Title (e.g. Python Developer, Full Stack Engineer)..."
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
              />
              <button
                className="action-btn match-btn"
                onClick={handleSkillMatch}
                disabled={isMatchingLoading}
              >
                {isMatchingLoading ? 'Matching Jobs...' : '🎯 Run Skill Match'}
              </button>
            </div>

            {matchingMessage && <div className="message">{matchingMessage}</div>}

            {matchedJobs.length > 0 && (
              <div className="jobs-grid">
                {matchedJobs.map((j, idx) => {
                  const score = j.match_score ?? j.overall_score ?? 0
                  const title = j.title || j.job_title || 'Software Engineer'
                  const company = j.company || 'Tech Company'
                  const location = j.location || 'Remote'
                  const matchingSkills = j.matched_skills || []
                  const missingSkills = j.missing_skills || j.unmatched_skills || []

                  return (
                    <div key={j.job_id || idx} className="job-card">
                      <div className="job-header">
                        <div>
                          <h3>{title}</h3>
                          <span className="company">{company} • {location}</span>
                        </div>
                        <div className={`score-badge ${score >= 70 ? 'high' : score >= 40 ? 'med' : 'low'}`}>
                          {Math.round(score)}% Match
                        </div>
                      </div>

                      <div className="skills-block">
                        <div>
                          <strong>Matching Skills:</strong>
                          <div className="tag-group">
                            {matchingSkills.map((s) => (
                              <span key={s} className="tag green">{s}</span>
                            ))}
                            {!matchingSkills.length && <span className="none-text">None</span>}
                          </div>
                        </div>

                        <div>
                          <strong>Missing Skills:</strong>
                          <div className="tag-group">
                            {missingSkills.map((s) => (
                              <span key={s} className="tag orange">{s}</span>
                            ))}
                            {!missingSkills.length && <span className="none-text">None</span>}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Step 3: Gap Analysis Action & Results */}
        {hasParsedProfile && (
          <div className="step-section">
            <div className="step-header">
              <h2>Step 3: Gap Analysis Agent & AI Reasoning</h2>
              <p>Analyze skill readiness score, priority skill gaps, and Gemini AI career focus.</p>
            </div>

            <button
              className="action-btn gap-btn"
              onClick={handleGapAnalysis}
              disabled={isGapLoading || !matchedJobs.length}
            >
              {isGapLoading ? 'Analyzing Skill Gaps...' : '📊 Run Gap Analysis'}
            </button>
            {!matchedJobs.length && (
              <span className="hint-text"> (Run Step 2 Skill Match first to enable Gap Analysis)</span>
            )}

            {gapMessage && <div className="message">{gapMessage}</div>}

            {gapAnalysis && (
              <div className="gap-results">
                {/* Aggregate Metadata Card */}
                <div className="metrics-card">
                  <div className="metric">
                    <span className="metric-label">Average Readiness Score</span>
                    <strong className="metric-val">{Math.round(gapAnalysis.metadata?.avg_readiness_score || 0)}%</strong>
                  </div>
                  <div className="metric">
                    <span className="metric-label">Jobs Analyzed</span>
                    <strong className="metric-val">{gapAnalysis.analyses?.length || 0}</strong>
                  </div>
                </div>

                {/* Per Job Analysis & AI Reasoning */}
                {gapAnalysis.analyses?.map((an, idx) => (
                  <div key={an.job_id || idx} className="analysis-card">
                    <div className="analysis-header">
                      <h3>{an.job_title}</h3>
                      <span className={`priority-badge ${an.gap_priority?.toLowerCase()}`}>
                        Gap Priority: {an.gap_priority}
                      </span>
                    </div>

                    <p className="explanation">{an.gap_explanation}</p>

                    {/* AI Reasoning Section */}
                    {an.ai_reasoning && (
                      <div className="ai-box">
                        <div className="ai-title">🤖 Gemini 3.6 AI Guidance</div>
                        <p><strong>Summary:</strong> {an.ai_reasoning.summary}</p>

                        {an.ai_reasoning.strengths?.length > 0 && (
                          <div>
                            <strong>Candidate Strengths:</strong>
                            <ul>
                              {an.ai_reasoning.strengths.map((st, i) => (
                                <li key={i}>{st}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {an.ai_reasoning.learning_focus?.length > 0 && (
                          <div>
                            <strong>Recommended Learning Focus:</strong>
                            <ul>
                              {an.ai_reasoning.learning_focus.map((lf, i) => (
                                <li key={i}>{lf}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {hasParsedProfile && (
          <div className="footer-reset-container">
            <button className="analyze-more-btn primary" onClick={handleReset}>
              ✨ Analyze Another Resume (Clean All)
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
