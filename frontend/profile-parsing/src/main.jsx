import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'
import { AgentWorkingWidget } from './AgentWorkingWidget'
import { generatePdfReport } from './reportAgent'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function App() {
  const [mode, setMode] = React.useState('file')
  const [file, setFile] = React.useState(null)
  const [text, setText] = React.useState('')
  const [profile, setProfile] = React.useState(null)
  const [targetRole, setTargetRole] = React.useState('')
  const [location, setLocation] = React.useState('')
  const [workflow, setWorkflow] = React.useState(null)
  const [notice, setNotice] = React.useState(null)
  const fileRef = React.useRef(null)

  // Agent Pipeline Drawer States
  const [widgetOpen, setWidgetOpen] = React.useState(false)
  const [currentStepIndex, setCurrentStepIndex] = React.useState(0)
  const [activeAgentName, setActiveAgentName] = React.useState('')
  const [widgetLogs, setWidgetLogs] = React.useState([])
  const [isFinished, setIsFinished] = React.useState(false)
  const [widgetError, setWidgetError] = React.useState(null)

  const matchedJobs = workflow?.matched_jobs || workflow?.matching_results || []
  const gaps = workflow?.skill_gaps || workflow?.gap_analyses || []
  const opportunities = workflow?.opportunity_analysis?.opportunities || []
  const courses = workflow?.training_recommendations || []
  const missingSkills = [...new Set(gaps.flatMap((gap) => gap.missing_skills || []))]
  const currentJobs = workflow?.current_jobs ?? workflow?.opportunity_analysis?.current_jobs ?? 0

  const addLog = (agent, message, type = 'info') => {
    const timeStr = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })
    setWidgetLogs((prev) => [...prev, { time: timeStr, agent, message, type }])
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

  // Continuous Single-Pass Multi-Agent Workflow Execution
  async function runFullAgentPipeline() {
    setNotice(null)
    setCurrentStepIndex(0)
    setActiveAgentName('Document Extractor Agent')
    setWidgetLogs([])
    setIsFinished(false)
    setWidgetError(null)
    setWidgetOpen(true)

    try {
      // Step 0: Document Extractor Agent
      addLog('Document Extractor Agent', 'Initializing document stream reader...', 'info')
      await sleep(400)

      let parseResponse
      if (mode === 'file') {
        if (!file) throw new Error('Please select a resume file first.')
        addLog('Document Extractor Agent', `Reading document bytes: "${file.name}" (${(file.size / 1024).toFixed(1)} KB)...`, 'info')
        const body = new FormData()
        body.append('file', file)

        // Step 1: Profile Extractor Agent (Gemini 3.6)
        setCurrentStepIndex(1)
        setActiveAgentName('Profile Extractor Agent (Gemini 3.6)')
        addLog('Profile Extractor Agent (Gemini 3.6)', 'Parsing resume text & extracting candidate skills with Gemini 3.6 Vision AI...', 'info')
        parseResponse = await fetch(`${API_BASE_URL}/api/profile/parse`, { method: 'POST', body })
      } else {
        if (!text.trim()) throw new Error('Please paste resume text first.')
        addLog('Document Extractor Agent', 'Reading pasted raw resume text tokens...', 'info')

        // Step 1: Profile Extractor Agent (Gemini 3.6)
        setCurrentStepIndex(1)
        setActiveAgentName('Profile Extractor Agent (Gemini 3.6)')
        addLog('Profile Extractor Agent (Gemini 3.6)', 'Parsing resume text & extracting candidate skills with Gemini 3.6 LLM...', 'info')
        parseResponse = await fetch(`${API_BASE_URL}/api/profile/parse-text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        })
      }

      const parseData = await parseResponse.json()
      if (!parseResponse.ok) throw new Error(parseData.detail || 'Profile extraction failed.')

      const parsedProfile = parseData.profile || {}
      setProfile(parsedProfile)
      const selectedRole = targetRole || parsedProfile.target_role || parsedProfile.experience?.[0]?.role || ''
      const selectedLoc = location || parsedProfile.location || ''
      if (!targetRole) setTargetRole(selectedRole)
      if (!location) setLocation(selectedLoc)

      addLog('Profile Extractor Agent (Gemini 3.6)', `Extracted candidate profile: "${parsedProfile.name || 'Candidate'}". Skills count: ${(parsedProfile.skills || []).length}`, 'success')
      await sleep(600)

      // Step 2: Skill Match Agent
      setCurrentStepIndex(2)
      setActiveAgentName('Skill Match Agent (Jooble & Vector DB)')
      addLog('Skill Match Agent (Jooble & Vector DB)', `Searching live Jooble market job vector embeddings for "${selectedRole || 'Software Engineer'}"...`, 'info')
      await sleep(700)

      // Step 3: Gap Analysis Agent (LangGraph)
      setCurrentStepIndex(3)
      setActiveAgentName('Gap Analysis Agent (LangGraph)')
      addLog('Gap Analysis Agent (LangGraph)', 'Initializing 4-node LangGraph orchestration workflow...', 'info')
      addLog('Gap Analysis Agent (LangGraph)', 'Evaluating candidate skills matrix against market requirements...', 'info')

      const graphPromise = fetch(`${API_BASE_URL}/api/skill-gap/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...parsedProfile,
          skills: parsedProfile.skills || [],
          target_role: selectedRole,
          location: selectedLoc,
        }),
      })

      // Step 4: Opportunity Simulation Agent
      await sleep(750)
      setCurrentStepIndex(4)
      setActiveAgentName('Opportunity Simulation Agent')
      addLog('Opportunity Simulation Agent', 'Simulating missing skill permutations & job unlock growth impact...', 'info')

      // Step 5: Training Recommendation Agent (MCP)
      await sleep(750)
      setCurrentStepIndex(5)
      setActiveAgentName('Training Recommendation Agent (MCP)')
      addLog('Training Recommendation Agent (MCP)', 'Querying local course catalog MCP server for high-ROI training pathways...', 'info')

      // Step 6: Report Generation Agent
      await sleep(650)
      setCurrentStepIndex(6)
      setActiveAgentName('Report Generation Agent')
      addLog('Report Generation Agent', 'Compiling AI Career Report PDF payload & executive dashboard metrics...', 'info')

      const graphResponse = await graphPromise
      const workflowData = await graphResponse.json()
      if (!graphResponse.ok) throw new Error(workflowData.detail || 'Career path analysis failed.')

      addLog('Report Generation Agent', 'PDF Career Analysis Report compiled and ready for download!', 'success')
      addLog('Orchestrator Agent', 'All 7 multi-agent workflow nodes executed successfully!', 'success')
      await sleep(500)

      setWorkflow(workflowData)
      setIsFinished(true)
      setNotice({ type: 'success', text: 'Multi-Agent career workflow completed! Review your profile, matched jobs, skill gaps, and recommended training below.' })
    } catch (error) {
      setWidgetError(error.message)
      addLog('System Error', error.message, 'error')
      setNotice({ type: 'error', text: error.message })
    }
  }

  // Re-run analysis if target role/location is updated
  async function rerunCareerAnalysis() {
    if (!profile) return
    setNotice(null)
    setCurrentStepIndex(2)
    setActiveAgentName('Skill Match Agent (Jooble & Vector DB)')
    setWidgetLogs([])
    setIsFinished(false)
    setWidgetError(null)
    setWidgetOpen(true)

    try {
      addLog('Skill Match Agent (Jooble & Vector DB)', `Re-querying market jobs for updated target role: "${targetRole}"...`, 'info')
      await sleep(600)

      setCurrentStepIndex(3)
      setActiveAgentName('Gap Analysis Agent (LangGraph)')
      addLog('Gap Analysis Agent (LangGraph)', 'Re-executing LangGraph skill gap analysis...', 'info')

      const graphPromise = fetch(`${API_BASE_URL}/api/skill-gap/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...profile,
          skills: profile.skills || [],
          target_role: targetRole,
          location: location,
        }),
      })

      await sleep(650)
      setCurrentStepIndex(4)
      setActiveAgentName('Opportunity Simulation Agent')
      addLog('Opportunity Simulation Agent', 'Recalculating job unlock multipliers...', 'info')

      await sleep(650)
      setCurrentStepIndex(5)
      setActiveAgentName('Training Recommendation Agent (MCP)')
      addLog('Training Recommendation Agent (MCP)', 'Updating course recommendations...', 'info')

      const graphResponse = await graphPromise
      const workflowData = await graphResponse.json()
      if (!graphResponse.ok) throw new Error(workflowData.detail || 'Career analysis failed.')

      addLog('Orchestrator Agent', 'Updated career analysis workflow complete!', 'success')
      await sleep(400)

      setWorkflow(workflowData)
      setIsFinished(true)
      setNotice({ type: 'success', text: 'Updated career analysis complete!' })
    } catch (error) {
      setWidgetError(error.message)
      addLog('System Error', error.message, 'error')
      setNotice({ type: 'error', text: error.message })
    }
  }

  function reset() {
    setFile(null)
    setText('')
    setProfile(null)
    setTargetRole('')
    setLocation('')
    setWorkflow(null)
    setNotice(null)
    setWidgetOpen(false)
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div className="app-shell">
      {/* Floating Gemini-style Agent Transparency Working Drawer */}
      <AgentWorkingWidget
        isOpen={widgetOpen}
        currentStepIndex={currentStepIndex}
        activeAgentName={activeAgentName}
        logs={widgetLogs}
        isFinished={isFinished}
        error={widgetError}
        onComplete={() => setWidgetOpen(false)}
      />

      <header className="app-navbar">
        <div className="navbar-brand">
          <img src="/icon.png" alt="Pathwise Icon" className="brand-logo-img" />
          <strong>pathwise</strong>
        </div>

        <div className="nav-actions">
          {(widgetLogs.length > 0) && (
            <button className="ghost-button" onClick={() => setWidgetOpen(true)} title="View live agent working transparency drawer">
              ⚡ View Active Agents
            </button>
          )}
          <button className="quiet-button" onClick={reset} title="Reset session and start a new career assessment">
            <span aria-hidden="true">↻</span> Start New Assessment
          </button>
        </div>
      </header>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="kicker">AI Career & Skill Intelligence</p>
            <h1>Turn your resume into a sharper next career move.</h1>
          </div>
        </header>

        <section className="intake-layout">
          <div className="intake-panel">
            <PanelHeading number="1" title="Upload Resume" label="Step 1" />
            <p className="section-copy">Upload or paste your resume to map your career path.</p>
            
            <div className="mode-switch" role="tablist">
              <button className={mode === 'file' ? 'selected' : ''} onClick={() => setMode('file')}>Upload file</button>
              <button className={mode === 'text' ? 'selected' : ''} onClick={() => setMode('text')}>Paste text</button>
            </div>

            {mode === 'file' ? (
              <label className={`dropzone ${file ? 'has-file' : ''}`}>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,image/*"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
                <span className="drop-icon">↑</span>
                <strong>{file ? file.name : 'Drop resume file here'}</strong>
                <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB selected` : 'PDF, DOCX, TXT, PNG or JPG · up to 10 MB'}</span>
              </label>
            ) : (
              <textarea
                className="resume-textarea"
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Paste the full text of your resume here..."
              />
            )}

            <button className="accent-button full-width" onClick={runFullAgentPipeline}>
              Analyze Resume <span>⚡</span>
            </button>
          </div>

          <div className="profile-panel">
            <PanelHeading number="2" title="Target Preferences" label="Optional" optional />
            <p className="section-copy">Set a target role or location to customize job matching.</p>
            
            <label className="field-label" htmlFor="target-role">Target role</label>
            <input
              id="target-role"
              className="text-field"
              value={targetRole}
              onChange={(event) => setTargetRole(event.target.value)}
              placeholder="e.g. Backend Engineer"
            />

            <label className="field-label" htmlFor="location">Preferred location</label>
            <input
              id="location"
              className="text-field"
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              placeholder="e.g. Remote / Pune"
            />

            {profile ? (
              <div>
                <ProfileSnapshot profile={profile} />
                <button className="ghost-button full-width margin-top-sm" onClick={rerunCareerAnalysis}>
                  🔄 Refresh Analysis
                </button>
              </div>
            ) : (
              <div className="empty-snapshot">Extracted profile details will appear here.</div>
            )}
          </div>
        </section>

        {notice && (
          <div className={`notice ${notice.type}`} role="status">
            <span>{notice.type === 'success' ? '✓' : '!'}</span>
            <span>{notice.text}</span>
          </div>
        )}

        {workflow && (
          <ResultsDashboard
            profile={profile}
            targetRole={targetRole}
            location={location}
            workflow={workflow}
            matchedJobs={matchedJobs}
            gaps={gaps}
            opportunities={opportunities}
            courses={courses}
            currentJobs={currentJobs}
            missingSkills={missingSkills}
          />
        )}
      </main>
    </div>
  )
}

function PanelHeading({ number, title, label, optional }) {
  return (
    <div className="section-heading">
      <div>
        <span className="section-number">{number}</span>
        <h2>{title}</h2>
      </div>
      <span className={`micro-label ${optional ? 'optional' : ''}`}>{label}</span>
    </div>
  )
}

function ProfileSnapshot({ profile }) {
  const skills = profile.skills || []
  return (
    <div className="profile-snapshot">
      <div className="avatar">{(profile.name || 'C').slice(0, 1).toUpperCase()}</div>
      <div className="snapshot-main">
        <strong>{profile.name || 'Candidate profile'}</strong>
        <span>{profile.email || 'Contact details not detected'}</span>
        <div className="tag-row">
          {skills.slice(0, 5).map((skill) => (
            <span className="skill-tag" key={skill}>{skill}</span>
          ))}
          {skills.length > 5 && <span className="skill-tag muted">+{skills.length - 5}</span>}
        </div>
      </div>
    </div>
  )
}

function ResultsDashboard({ profile, targetRole, location, workflow, matchedJobs, gaps, opportunities, courses, currentJobs, missingSkills }) {
  return (
    <section className="results-area">
      <div className="results-header">
        <div>
          <p className="kicker">Multi-Agent Workflow Results</p>
          <h2>Here is what your resume means</h2>
        </div>
        <span className="source-pill">
          {workflow.job_source === 'jooble' ? 'Live Jooble Market API' : 'Demo job database'}
          <span className="online-dot" />
        </span>
      </div>

      <div className="metrics-row">
        <Metric label="Jobs that fit now" value={currentJobs} note="Your starting point" accent />
        <Metric label="Jobs checked" value={matchedJobs.length} note="Vector matched directions" />
        <Metric label="Skills to strengthen" value={missingSkills.length} note="Target learning list" />
        <Metric label="Courses suggested" value={courses.length} note="Curated next steps" />
      </div>

      <div className="results-grid">
        <section className="result-section">
          <SectionTitle number="A" title="Jobs that fit you" meta="Top Market Matches" />
          <p className="plain-helper">These are the roles closest to your current experience & skills vector.</p>
          <div className="job-list">
            {matchedJobs.slice(0, 6).map((job) => (
              <JobRow job={job} key={job.job_id || job.title} />
            ))}
            {!matchedJobs.length && <EmptyState text="No matching roles came back from this run." />}
          </div>
        </section>

        <section className="result-section">
          <SectionTitle number="B" title="Skills to strengthen" meta="Skill Gap Matrix" />
          <p className="plain-helper">Adding these skills can open more of the roles you want.</p>
          <div className="gap-list">
            {missingSkills.map((skill) => {
              const opportunity = opportunities.find((item) => item.skill === skill)
              return (
                <div className="gap-row" key={skill}>
                  <span className="gap-marker" />
                  <div>
                    <strong>{skill}</strong>
                    <span>{opportunity ? `Could open +${opportunity.jobs_unlocked} more jobs` : 'High priority for target role'}</span>
                  </div>
                </div>
              )
            })}
            {!missingSkills.length && <EmptyState text="You already cover the skills found in this run." />}
          </div>
        </section>
      </div>

      <section className="opportunity-section">
        <SectionTitle number="C" title="Opportunity Matrix & Job Unlock Impact" meta="Vector Market Simulation" />
        <p className="plain-helper">We simulated each missing skill combination against live market vector embeddings to measure job growth.</p>
        
        <div className="opportunity-grid">
          {opportunities.slice(0, 6).map((item) => (
            <div className="opportunity-card" key={item.skill}>
              <div className="op-card-header">
                <div className="op-skill-info">
                  <strong className="op-skill-name">{item.skill}</strong>
                  <span className="op-skill-time">
                    ⏱️ {item.duration_weeks ? `${item.duration_weeks} wks est. learning time` : 'Market demand signal'}
                  </span>
                </div>
                <div className="op-unlock-badge">
                  <span className="op-unlock-num">+{item.jobs_unlocked}</span>
                  <span className="op-unlock-label">unlocked</span>
                </div>
              </div>
              <div className="op-progress-track">
                <div 
                  className="op-progress-fill" 
                  style={{ width: `${Math.min(100, Math.max(25, (item.jobs_unlocked || 1) * 35))}%` }} 
                />
              </div>
            </div>
          ))}
          {!opportunities.length && <EmptyState text="No extra job opportunities detected in this simulation." />}
        </div>
      </section>

      <section className="learning-section">
        <SectionTitle number="D" title="Your training plan" meta="High-ROI Recommended Courses" />
        <p className="plain-helper">These course recommendations are chosen by the Training Agent to close your top skill gaps.</p>
        <div className="course-grid">
          {courses.map((course) => (
            <CourseCard course={course} key={course.course_name} />
          ))}
          {!courses.length && <EmptyState text="Your learning plan will appear when the workflow finds a course match." />}
        </div>
      </section>

      {/* PDF Report Generation & Download Section */}
      <section className="report-download-section">
        <div className="report-download-card">
          <div className="report-icon-badge">📄</div>
          <h3>AI Career Analysis Report</h3>
          <p>Download your complete PDF summary including job matches, skill gaps, and training pathways.</p>
          <button 
            className="accent-button download-pdf-btn" 
            onClick={() => generatePdfReport({ profile, workflow, targetRole, location })}
          >
            📥 Download Report (PDF)
          </button>
        </div>
      </section>
    </section>
  )
}

function Metric({ label, value, note, accent }) {
  return (
    <div className={`metric-card ${accent ? 'accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  )
}

function SectionTitle({ number, title, meta }) {
  return (
    <div className="result-title">
      <div>
        <span className="section-number">{number}</span>
        <h3>{title}</h3>
      </div>
      <span>{meta}</span>
    </div>
  )
}

function EmptyState({ text }) { return <div className="empty-state">{text}</div> }

function JobRow({ job }) {
  const score = Math.round(job.match_score || 0)
  return (
    <article className="job-row">
      <div className="job-score">{score}<small>%</small></div>
      <div className="job-info">
        <strong>{job.title || job.job_title || 'Untitled role'}</strong>
        <span>{job.company || 'Company undisclosed'} · {job.location || 'Location unknown'}</span>
        <div className="tag-row">
          {(job.matched_skills || []).slice(0, 3).map((skill) => (
            <span className="skill-tag" key={skill}>{skill}</span>
          ))}
          {job.location_compatibility && (
            <span className="skill-tag location-tag">{job.location_compatibility.replace('_', ' ')}</span>
          )}
        </div>
      </div>
    </article>
  )
}

function CourseCard({ course }) {
  return (
    <article className="course-card">
      <div className="course-topline">
        <span>Recommended course</span>
        <b>{course.learning_impact ?? '—'} impact</b>
      </div>
      <h3>{course.course_name}</h3>
      <p>{course.provider || 'Course catalog'} · {course.duration_weeks || '—'} weeks</p>
      <div className="course-stats">
        <strong>+{course.jobs_unlocked || 0}</strong>
        <span>jobs unlocked</span>
      </div>
      {course.reasoning && <blockquote>{course.reasoning}</blockquote>}
      {course.url && <a href={course.url} target="_blank" rel="noreferrer">View resource ↗</a>}
    </article>
  )
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
