import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const STEPS = [
  ['Your profile', 'What we found'],
  ['Your job fit', 'Where you stand'],
  ['What to learn', 'Skills to strengthen'],
  ['Your next steps', 'A practical plan'],
]

function App() {
  const [mode, setMode] = React.useState('file')
  const [file, setFile] = React.useState(null)
  const [text, setText] = React.useState('')
  const [profile, setProfile] = React.useState(null)
  const [targetRole, setTargetRole] = React.useState('')
  const [location, setLocation] = React.useState('')
  const [workflow, setWorkflow] = React.useState(null)
  const [busy, setBusy] = React.useState('')
  const [notice, setNotice] = React.useState(null)
  const fileRef = React.useRef(null)

  const matchedJobs = workflow?.matched_jobs || workflow?.matching_results || []
  const gaps = workflow?.skill_gaps || workflow?.gap_analyses || []
  const opportunities = workflow?.opportunity_analysis?.opportunities || []
  const courses = workflow?.training_recommendations || []
  const missingSkills = [...new Set(gaps.flatMap((gap) => gap.missing_skills || []))]
  const currentJobs = workflow?.current_jobs ?? workflow?.opportunity_analysis?.current_jobs ?? 0

  async function parseResume() {
    setNotice(null)
    setBusy('parse')
    try {
      let response
      if (mode === 'file') {
        if (!file) throw new Error('Choose a resume file first.')
        const body = new FormData()
        body.append('file', file)
        response = await fetch(`${API_BASE_URL}/api/profile/parse`, { method: 'POST', body })
      } else {
        if (!text.trim()) throw new Error('Paste resume text first.')
        response = await fetch(`${API_BASE_URL}/api/profile/parse-text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        })
      }
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Resume parsing failed.')
      const parsed = data.profile || {}
      setProfile(parsed)
      setTargetRole(parsed.target_role || parsed.experience?.[0]?.role || '')
      setLocation(parsed.location || '')
      setWorkflow(null)
      setNotice({ type: 'success', text: 'Profile ready. Review the details, then run the career analysis.' })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy('')
    }
  }

  async function runAnalysis() {
    if (!profile) return
    setNotice(null)
    setBusy('analysis')
    try {
      const response = await fetch(`${API_BASE_URL}/api/skill-gap/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...profile,
          skills: profile.skills || [],
          target_role: targetRole || profile.target_role || '',
          location: location || profile.location || '',
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Career analysis failed.')
      setWorkflow(data)
      setNotice({ type: 'success', text: 'Your career path has been mapped.' })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setBusy('')
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
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div className="app-shell">
      <header className="app-navbar">
        <div className="navbar-brand"><div className="brand-mark">p</div><strong>pathwise</strong></div>
        <Journey profile={profile} workflow={workflow} />
        <button className="quiet-button" onClick={reset} title="Start a new analysis"><span aria-hidden="true">↻</span> New analysis</button>
      </header>
      <main className="main-content">
        <header className="topbar">
          <div><p className="kicker">A simple journey from resume to training plan</p><h1>Turn your resume into a sharper next move.</h1></div>
        </header>

        <section className="intake-layout">
          <div className="intake-panel">
            <PanelHeading number="1" title="Start with your resume" label="First step" />
            <p className="section-copy">Upload your resume or paste its text. We will read the important details for you.</p>
            <div className="mode-switch" role="tablist">
              <button className={mode === 'file' ? 'selected' : ''} onClick={() => setMode('file')}>Upload file</button>
              <button className={mode === 'text' ? 'selected' : ''} onClick={() => setMode('text')}>Paste text</button>
            </div>
            {mode === 'file' ? <label className={`dropzone ${file ? 'has-file' : ''}`}><input ref={fileRef} type="file" accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp,.bmp,.tiff,image/*" onChange={(event) => setFile(event.target.files?.[0] || null)} /><span className="drop-icon">↑</span><strong>{file ? file.name : 'Drop your resume here'}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB selected` : 'PDF, DOCX, TXT, PNG or JPG · up to 10 MB'}</span></label> : <textarea className="resume-textarea" value={text} onChange={(event) => setText(event.target.value)} placeholder="Paste the full text of your resume here..." />}
            <button className="accent-button full-width" onClick={parseResume} disabled={busy === 'parse'}>{busy === 'parse' ? 'Reading profile...' : 'Create profile'} <span>→</span></button>
          </div>

          <div className="profile-panel">
            <PanelHeading number="2" title="Tell us where you want to go" label="Optional" optional />
            <p className="section-copy">Add a role or place if you already have one in mind. You can leave these blank.</p>
            <label className="field-label" htmlFor="target-role">Target role</label>
            <input id="target-role" className="text-field" value={targetRole} onChange={(event) => setTargetRole(event.target.value)} placeholder="e.g. Backend Engineer" />
            <label className="field-label" htmlFor="location">Preferred location</label>
            <input id="location" className="text-field" value={location} onChange={(event) => setLocation(event.target.value)} placeholder="e.g. Pune or Remote" />
            {profile ? <ProfileSnapshot profile={profile} /> : <div className="empty-snapshot">Your extracted profile will appear here.</div>}
          </div>
        </section>

        {notice && <div className={`notice ${notice.type}`} role="status">{notice.type === 'success' ? '✓' : '!'} {notice.text}</div>}
        {profile && <section className="analysis-launch"><div><span className="section-number">3</span><h2>See your path</h2><p>We will compare your experience with jobs, explain what is missing, and create your learning plan.</p></div><button className="accent-button" onClick={runAnalysis} disabled={busy === 'analysis'}>{busy === 'analysis' ? 'Building your path...' : 'Show my career path'} <span>↗</span></button></section>}
        {busy === 'analysis' && <div className="loading-rail"><span className="spinner" /> Comparing your profile with the live workflow...</div>}
        {workflow && <ResultsDashboard workflow={workflow} matchedJobs={matchedJobs} gaps={gaps} opportunities={opportunities} courses={courses} currentJobs={currentJobs} missingSkills={missingSkills} />}
      </main>
    </div>
  )
}

function PanelHeading({ number, title, label, optional }) { return <div className="section-heading"><div><span className="section-number">{number}</span><h2>{title}</h2></div><span className={`micro-label ${optional ? 'optional' : ''}`}>{label}</span></div> }
function Journey({ profile, workflow }) {
  return <section className="journey" aria-label="Your journey">
    <div className="journey-line" />
    {STEPS.map(([title, subtitle], index) => {
      const active = index === 0 ? Boolean(profile) : Boolean(workflow)
      const locked = index > 0 && !workflow
      return <div className={`journey-step ${active ? 'active' : ''} ${locked ? 'locked' : ''}`} aria-current={active && index === (workflow ? 3 : 0) ? 'step' : undefined} key={title}><div className="journey-light">{active ? '✓' : locked ? '🔒' : index + 1}</div><strong>{title}</strong><span>{locked ? 'Locked' : subtitle}</span></div>
    })}
  </section>
}
function ProfileSnapshot({ profile }) { const skills = profile.skills || []; return <div className="profile-snapshot"><div className="avatar">{(profile.name || 'C').slice(0, 1).toUpperCase()}</div><div className="snapshot-main"><strong>{profile.name || 'Candidate profile'}</strong><span>{profile.email || 'Contact details not detected'}</span><div className="tag-row">{skills.slice(0, 5).map((skill) => <span className="skill-tag" key={skill}>{skill}</span>)}{skills.length > 5 && <span className="skill-tag muted">+{skills.length - 5}</span>}</div></div></div> }

function ResultsDashboard({ workflow, matchedJobs, gaps, opportunities, courses, currentJobs, missingSkills }) {
  return <section className="results-area"><div className="results-header"><div><p className="kicker">Your results</p><h2>Here is what your resume means</h2></div><span className="source-pill">{workflow.job_source === 'jooble' ? 'Live job market' : 'Demo market'} <span className="online-dot" /></span></div><div className="metrics-row"><Metric label="Jobs that fit now" value={currentJobs} note="your starting point" accent /><Metric label="Jobs checked" value={matchedJobs.length} note="possible directions" /><Metric label="Skills to strengthen" value={missingSkills.length} note="your learning list" /><Metric label="Courses suggested" value={courses.length} note="your next steps" /></div><div className="results-grid"><section className="result-section"><SectionTitle number="A" title="Jobs that fit you" meta="Start here" /><p className="plain-helper">These are the roles closest to your current experience.</p><div className="job-list">{matchedJobs.slice(0, 6).map((job) => <JobRow job={job} key={job.job_id} />)}{!matchedJobs.length && <EmptyState text="No matching roles came back from this run." />}</div></section><section className="result-section"><SectionTitle number="B" title="Skills to strengthen" meta="What is missing" /><p className="plain-helper">Adding these skills can open more of the roles you want.</p><div className="gap-list">{missingSkills.map((skill) => { const opportunity = opportunities.find((item) => item.skill === skill); return <div className="gap-row" key={skill}><span className="gap-marker" /><div><strong>{skill}</strong><span>{opportunity ? `Could open ${opportunity.jobs_unlocked} more jobs` : 'Useful for your target'}</span></div></div> })}{!missingSkills.length && <EmptyState text="You already cover the skills found in this run." />}</div></section></div><section className="opportunity-band"><div className="opportunity-intro"><span className="section-number">C</span><h2>What could help most?</h2><p>We tested each missing skill against the same job matcher.</p></div><div className="opportunity-list">{opportunities.slice(0, 4).map((item) => <div className="opportunity-item" key={item.skill}><div><strong>{item.skill}</strong><span>{item.duration_weeks ? `${item.duration_weeks} weeks · ${item.learning_impact} jobs/week` : 'market signal'}</span></div><b>+{item.jobs_unlocked}</b></div>)}{!opportunities.length && <span className="muted-copy">No extra job opportunities were detected yet.</span>}</div></section><section className="learning-section"><SectionTitle number="D" title="Your training plan" meta="Do this next" /><p className="plain-helper">These recommendations are chosen to help you close the most useful gaps.</p><div className="course-grid">{courses.map((course) => <CourseCard course={course} key={course.course_name} />)}{!courses.length && <EmptyState text="Your learning plan will appear when the workflow finds a course match." />}</div></section></section>
}

function Metric({ label, value, note, accent }) { return <div className={`metric-card ${accent ? 'accent' : ''}`}><span>{label}</span><strong>{value}</strong><small>{note}</small></div> }
function SectionTitle({ number, title, meta }) { return <div className="result-title"><div><span className="section-number">{number}</span><h3>{title}</h3></div><span>{meta}</span></div> }
function EmptyState({ text }) { return <div className="empty-state">{text}</div> }
function JobRow({ job }) { const score = Math.round(job.match_score || 0); return <article className="job-row"><div className="job-score">{score}<small>%</small></div><div className="job-info"><strong>{job.title || job.job_title || 'Untitled role'}</strong><span>{job.company || 'Company undisclosed'} · {job.location || 'Location unknown'}</span><div className="tag-row">{(job.matched_skills || []).slice(0, 3).map((skill) => <span className="skill-tag" key={skill}>{skill}</span>)}{job.location_compatibility && <span className="skill-tag location-tag">{job.location_compatibility.replace('_', ' ')}</span>}</div></div></article> }
function CourseCard({ course }) { return <article className="course-card"><div className="course-topline"><span>Recommended course</span><b>{course.learning_impact ?? '—'} impact</b></div><h3>{course.course_name}</h3><p>{course.provider || 'Course catalog'} · {course.duration_weeks || '—'} weeks</p><div className="course-stats"><strong>+{course.jobs_unlocked || 0}</strong><span>jobs unlocked</span></div>{course.reasoning && <blockquote>{course.reasoning}</blockquote>}{course.url && <a href={course.url} target="_blank" rel="noreferrer">View resource ↗</a>}</article> }

ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><App /></React.StrictMode>)
