import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'
import { AgentWorkingWidget } from './AgentWorkingWidget'
import { generatePdfReport } from './reportAgent'
import { SkillGapChart, OpportunityUnlockChart, SkillCoverageChart } from './CareerIntelligenceCharts'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function App() {
  const [mode, setMode] = React.useState('file')
  const [file, setFile] = React.useState(null)
  const [text, setText] = React.useState('')
  const [voiceTranscript, setVoiceTranscript] = React.useState('')
  const [isRecording, setIsRecording] = React.useState(false)
  const [profile, setProfile] = React.useState(null)
  const [targetRole, setTargetRole] = React.useState('')
  const [location, setLocation] = React.useState('')
  const [freeOnly, setFreeOnly] = React.useState(false)
  const [workflow, setWorkflow] = React.useState(null)
  const [careerSimulator, setCareerSimulator] = React.useState(null)
  const [simulatorInput, setSimulatorInput] = React.useState('')
  const [simulatorBusy, setSimulatorBusy] = React.useState(false)
  const [notice, setNotice] = React.useState(null)
  const fileRef = React.useRef(null)
  const recognitionRef = React.useRef(null)

  // Agent Pipeline Drawer States
  const [widgetOpen, setWidgetOpen] = React.useState(false)
  const [progressEvents, setProgressEvents] = React.useState([])
  const [runStatus, setRunStatus] = React.useState('idle')
  const [progressDisconnected, setProgressDisconnected] = React.useState(false)
  const [widgetError, setWidgetError] = React.useState(null)
  const eventSourceRef = React.useRef(null)
  const [chatOpen, setChatOpen] = React.useState(false)
  const [chatInput, setChatInput] = React.useState('')
  const [chatMessages, setChatMessages] = React.useState([])
  const autoSimulationRunRef = React.useRef('')

  const matchedJobs = workflow?.matched_jobs || workflow?.matching_results || []
  const gaps = workflow?.skill_gaps || workflow?.gap_analyses || []
  const opportunities = workflow?.opportunity_analysis?.opportunities || []
  const opportunityDiscovery = workflow?.opportunity_discovery || workflow?.opportunity_analysis?.opportunity_discovery || {
    current_matching_jobs: workflow?.current_jobs ?? workflow?.opportunity_analysis?.current_jobs ?? 0,
    skill_opportunities: [],
    recommended_sequence: [],
    cumulative_plan: [],
    total_jobs_unlocked: 0,
    total_learning_weeks: 0,
    total_cost_inr: 0,
  }
  const missingSkills = [...new Set(gaps.flatMap((gap) => (gap.missing_skills || []).map((s) => (typeof s === 'string' ? s : s?.skill || String(s || '')))).filter(Boolean))]
  const missingSkillKeys = missingSkills.map((skill) => String(skill || '').toLowerCase())
  const courses = workflow?.training_recommendations?.length
    ? workflow.training_recommendations
    : (workflow?.course_catalog || []).filter((course) =>
        (course.skills_taught || []).some((skill) => missingSkillKeys.some((missing) => {
          const courseSkill = String(skill).toLowerCase()
          return courseSkill === missing || courseSkill.includes(missing) || missing.includes(courseSkill)
        }))
      ).map((course) => ({
        ...course,
        course_name: course.title,
        jobs_unlocked: 0,
        learning_impact: null,
        reasoning: 'Available from the PathWise course catalog.',
        }))
  const currentJobs = workflow?.current_jobs ?? workflow?.opportunity_analysis?.current_jobs ?? 0

  const [widgetLogs, setWidgetLogs] = React.useState([])
  const [currentStepIndex, setCurrentStepIndex] = React.useState(0)
  const [activeAgentName, setActiveAgentName] = React.useState('')
  const [isFinished, setIsFinished] = React.useState(false)

  const closeEventSource = () => {
    if (eventSourceRef.current) eventSourceRef.current.close()
    eventSourceRef.current = null
  }

  React.useEffect(() => {
    if (notice?.type !== 'info') return undefined
    const timer = window.setTimeout(() => setNotice(null), 10000)
    return () => window.clearTimeout(timer)
  }, [notice])

  React.useEffect(() => {
    const defaultSkills = missingSkills.slice(0, 4).join(', ')
    if (!simulatorInput && defaultSkills) {
      setSimulatorInput(defaultSkills)
    }
  }, [missingSkills, simulatorInput])

  React.useEffect(() => {
    if (workflow?.career_simulator) {
      setCareerSimulator(workflow.career_simulator)
    }
  }, [workflow])

  async function runCareerSimulator(skillsOverride = null) {
    if (!profile) return
    setSimulatorBusy(true)
    setNotice(null)

    try {
      const body = {
        skills: profile.skills || [],
        target_role: targetRole || profile.target_role || '',
        location: location || profile.location || '',
        interests: profile.interests || [],
        free_only: freeOnly,
        add_skills: (skillsOverride || simulatorInput.split(',')).map((item) => item.trim()).filter(Boolean),
      }
      const response = await fetch(`${API_BASE_URL}/api/career-simulator/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Career simulator failed.')
      setCareerSimulator(data.career_simulator)
      setNotice({ type: 'success', text: 'What-if simulation updated for the selected learning plan.' })
    } catch (error) {
      setNotice({ type: 'error', text: error.message })
    } finally {
      setSimulatorBusy(false)
    }
  }

  const addLog = (agent, message, type = 'info') => {
    const timeStr = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })
    setWidgetLogs((prev) => [...prev, { time: timeStr, agent, message, type }])
  }

  React.useEffect(() => () => closeEventSource(), [])

  function appendProgressEvent(node, label, status, message, eventType = 'progress') {
    setProgressEvents((previous) => [...previous, {
      run_id: 'local-upload',
      event_type: eventType,
      node,
      label,
      status,
      message,
      timestamp: new Date().toISOString(),
      data: {},
    }])
  }

  async function startWorkflowRun(payload, successText, preserveProgressEvents = false, preserveNotice = false) {
    closeEventSource()
    if (!preserveNotice) setNotice(null)
    if (!preserveProgressEvents) setProgressEvents([])
    setRunStatus('starting')
    setProgressDisconnected(false)
    setWidgetError(null)
    setWidgetOpen(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/skill-gap/analyze/run`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      const data = await response.json()
      if (!response.ok || !data.run_id) throw new Error(data.detail || 'Could not start career analysis.')
      setRunStatus('running')
      const source = new EventSource(`${API_BASE_URL}/api/agent/progress/${data.run_id}`)
      eventSourceRef.current = source
      const handleProgress = (message) => {
        try { setProgressEvents((previous) => [...previous, JSON.parse(message.data)]) } catch { /* ignore malformed reconnect data */ }
      }
      source.addEventListener('progress', handleProgress)
      source.addEventListener('complete', async (message) => {
        try {
          const event = JSON.parse(message.data)
          setProgressEvents((previous) => [...previous, event])
          let result = null
          for (let attempt = 0; attempt < 5; attempt++) {
            const resultResponse = await fetch(`${API_BASE_URL}/api/agent/runs/${data.run_id}`)
            if (resultResponse.ok) {
              const resData = await resultResponse.json()
              if (resData && resData.status !== 'running') {
                result = resData
                break
              }
            }
            await new Promise((resolve) => setTimeout(resolve, 400))
          }
          if (!result) {
            const fallbackResp = await fetch(`${API_BASE_URL}/api/agent/runs/${data.run_id}`)
            result = await fallbackResp.json()
          }
          if (!result || result.status === 'error') {
            throw new Error(result?.detail || 'Workflow returned an error state.')
          }
          setWorkflow(result)
          setRunStatus('completed')
          closeEventSource()
          const warningNote = result.warnings?.length ? ` ${result.warnings.length} recoverable issue${result.warnings.length === 1 ? '' : 's'} handled.` : ''
          if (successText) setNotice({ type: 'success', text: `${successText}${warningNote}` })
        } catch (err) {
          console.error('Error loading workflow results:', err)
          setWidgetError(err.message)
          setRunStatus('failed')
          closeEventSource()
        }
      })
      source.addEventListener('error', (message) => {
        if (message?.data) {
          try { setProgressEvents((previous) => [...previous, JSON.parse(message.data)]) } catch { /* ignore */ }
          setRunStatus('failed')
          setWidgetError('The career workflow failed. Review the live log for details.')
          closeEventSource()
        } else {
          // Normal connection closure from completed stream
          setProgressDisconnected(true)
        }
      })
    } catch (error) {
      setRunStatus('failed')
      setWidgetError(error.message)
      setNotice({ type: 'error', text: error.message })
    }
  }

  const mediaRecorderRef = React.useRef(null)
  const audioChunksRef = React.useRef([])
  const audioFileRef = React.useRef(null)
  const [isTranscribing, setIsTranscribing] = React.useState(false)
  const [liveInterim, setLiveInterim] = React.useState('')

  async function toggleVoiceRecording() {
    if (isRecording) {
      mediaRecorderRef.current?.stop()
      recognitionRef.current?.stop()
      setIsRecording(false)
      setLiveInterim('')
      return
    }

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setNotice({ type: 'error', text: 'Microphone access denied. Please allow mic permissions and try again.' })
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition()
      recognition.lang = 'en-US'
      recognition.continuous = true
      recognition.interimResults = true
      recognitionRef.current = recognition
      recognition.onresult = (e) => {
        let interim = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          if (!e.results[i].isFinal) interim += e.results[i][0].transcript
        }
        setLiveInterim(interim)
      }
      recognition.onerror = () => {}
      recognition.start()
    }

    audioChunksRef.current = []
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'

    const recorder = new MediaRecorder(stream, { mimeType })
    mediaRecorderRef.current = recorder

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunksRef.current.push(e.data)
    }

    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop())
      setLiveInterim('')

      const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
      audioChunksRef.current = []

      if (blob.size < 1000) {
        setNotice({ type: 'error', text: 'Recording was too short. Please speak for at least a second.' })
        return
      }

      await sendAudioToBackend(blob, 'recording.webm')
    }

    recorder.start(250)
    setIsRecording(true)
  }

  async function sendAudioToBackend(audioBlob, filename = 'recording.webm') {
    setIsTranscribing(true)
    try {
      const form = new FormData()
      form.append('audio', audioBlob, filename)
      const res = await fetch(`${API_BASE_URL}/api/voice/transcribe`, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Transcription failed.')
      setVoiceTranscript((prev) => (prev ? prev + ' ' + data.transcript : data.transcript))
    } catch (err) {
      setNotice({ type: 'error', text: `Transcription error: ${err.message}` })
    } finally {
      setIsTranscribing(false)
    }
  }

  async function handleAudioFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    await sendAudioToBackend(file, file.name)
    if (audioFileRef.current) audioFileRef.current.value = ''
  }

  async function runFullAgentPipeline() {
    if (runStatus === 'running' || runStatus === 'starting') return
    setNotice(null)
    setProgressEvents([])
    setRunStatus('starting')
    setProgressDisconnected(false)
    setWidgetError(null)
    setWidgetOpen(true)
    let documentParseStarted = false
    let documentParseCompleted = false
    try {
      let parseResponse
      if (mode === 'file') {
        if (!file) throw new Error('Please select a resume file first.')
        setChatMessages([])
        setChatOpen(true)
        setNotice({ type: 'info', text: 'Until the response is generated, you can talk with the chat assistant. Its results are based on your resume.' })
        documentParseStarted = true
        appendProgressEvent('profile_parsing', 'Document Extractor', 'running', `Uploading and reading "${file.name}"...`)
        const body = new FormData(); body.append('file', file)
        parseResponse = await fetch(`${API_BASE_URL}/api/profile/parse`, { method: 'POST', body })
      } else if (mode === 'voice') {
        if (!voiceTranscript.trim()) throw new Error('Please record your resume details using voice first.')
        setChatMessages([])
        setChatOpen(true)
        setNotice({ type: 'info', text: 'Until the response is generated, you can talk with the chat assistant. Its results are based on your resume.' })
        addLog('Document Extractor Agent', 'Processing voice transcript tokens...', 'info')
        setCurrentStepIndex(1)
        setActiveAgentName('Profile Extractor Agent (Gemini 3.6)')
        addLog('Profile Extractor Agent (Gemini 3.6)', 'Parsing voice transcript & extracting candidate skills with Gemini 3.6 LLM...', 'info')
        parseResponse = await fetch(`${API_BASE_URL}/api/profile/parse-text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: voiceTranscript }),
        })
      } else {
        if (!text.trim()) throw new Error('Please paste resume text first.')
        setChatMessages([])
        setChatOpen(true)
        setNotice({ type: 'info', text: 'Until the response is generated, you can talk with the chat assistant. Its results are based on your resume.' })
        parseResponse = await fetch(`${API_BASE_URL}/api/profile/parse-text`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) })
      }
      const parseData = await parseResponse.json()
      if (!parseResponse.ok) throw new Error(parseData.detail || 'Profile extraction failed.')
      const parsedProfile = parseData.profile || {}
      if (mode === 'file') {
        documentParseCompleted = true
        appendProgressEvent('profile_parsing', 'Document Extractor', 'completed', `Document read and profile extracted from "${file.name}".`)
      }
      setProfile(parsedProfile)
      const selectedRole = targetRole || parsedProfile.target_role || parsedProfile.experience?.[0]?.role || ''
      const selectedLoc = location || parsedProfile.location || ''
      if (!targetRole) setTargetRole(selectedRole)
      if (!location) setLocation(selectedLoc)

      addLog('Profile Extractor Agent (Gemini 3.6)', `Extracted candidate profile: "${parsedProfile.name || 'Candidate'}". Skills count: ${(parsedProfile.skills || []).length}`, 'success')
      setCurrentStepIndex(2)
      setActiveAgentName('Skill Match Agent (Jooble & Vector DB)')
      addLog('Skill Match Agent (Jooble & Vector DB)', `Searching live Jooble market job vector embeddings for "${selectedRole || 'Software Engineer'}"...`, 'info')

      await startWorkflowRun({ ...parsedProfile, skills: parsedProfile.skills || [], target_role: selectedRole, location: selectedLoc, free_only: freeOnly }, '', true, true)

      setCurrentStepIndex(3)
      setActiveAgentName('Gap Analysis Agent (LangGraph)')
      addLog('Gap Analysis Agent (LangGraph)', 'Evaluating candidate skills matrix against market requirements...', 'info')
      setCurrentStepIndex(4)
      setActiveAgentName('Opportunity Simulation Agent')
      addLog('Opportunity Simulation Agent', 'Simulating missing skill permutations & job unlock growth impact...', 'info')
      setCurrentStepIndex(5)
      setActiveAgentName('Training Recommendation Agent (MCP)')
      addLog('Training Recommendation Agent (MCP)', 'Querying course catalog for high-ROI training pathways...', 'info')
      setCurrentStepIndex(6)
      setActiveAgentName('Report Generation Agent')
      addLog('Report Generation Agent', 'Compiling AI Career Report & dashboard metrics...', 'info')
      addLog('Report Generation Agent', 'Career Report ready for download & view!', 'success')
      addLog('Orchestrator Agent', 'All multi-agent workflow nodes executed successfully!', 'success')
      setIsFinished(true)
    } catch (error) {
      if (documentParseStarted && !documentParseCompleted) {
        appendProgressEvent('profile_parsing', 'Document Extractor', 'failed', error.message, 'error')
      }
      setRunStatus('failed')
      setWidgetError(error.message)
      setWidgetOpen(true)
      setNotice({ type: 'error', text: error.message })
    }
  }

  async function rerunCareerAnalysis() {
    if (!profile || runStatus === 'running' || runStatus === 'starting') return
    setNotice(null)
    setCurrentStepIndex(2)
    setActiveAgentName('Skill Match Agent (Jooble & Vector DB)')
    setWidgetLogs([])
    setIsFinished(false)
    setWidgetError(null)
    setWidgetOpen(true)

    try {
      addLog('Skill Match Agent (Jooble & Vector DB)', `Re-querying market jobs for updated target role: "${targetRole}"...`, 'info')
      setCurrentStepIndex(3)
      setActiveAgentName('Gap Analysis Agent (LangGraph)')
      addLog('Gap Analysis Agent (LangGraph)', 'Re-executing LangGraph skill gap analysis...', 'info')
      await startWorkflowRun({ ...profile, skills: profile.skills || [], target_role: targetRole, location, free_only: freeOnly }, 'Updated career analysis complete!')
      setCurrentStepIndex(4)
      setActiveAgentName('Opportunity Simulation Agent')
      addLog('Opportunity Simulation Agent', 'Recalculating job unlock multipliers...', 'info')
      setCurrentStepIndex(5)
      setActiveAgentName('Training Recommendation Agent (MCP)')
      addLog('Training Recommendation Agent (MCP)', 'Updating course recommendations...', 'info')
      addLog('Orchestrator Agent', 'Updated career analysis workflow complete!', 'success')
      setIsFinished(true)
      setNotice({ type: 'success', text: 'Updated career analysis complete!' })
    } catch (error) {
      setWidgetError(error.message)
      addLog('System Error', error.message, 'error')
      setNotice({ type: 'error', text: error.message })
    }
  }

  function reset() {
    closeEventSource()
    mediaRecorderRef.current?.stop()
    recognitionRef.current?.stop()
    setFile(null)
    setText('')
    setVoiceTranscript('')
    setIsRecording(false)
    setIsTranscribing(false)
    setLiveInterim('')
    setProfile(null)
    setTargetRole('')
    setLocation('')
    setFreeOnly(false)
    setWorkflow(null)
    setCareerSimulator(null)
    setSimulatorInput('')
    setSimulatorBusy(false)
    setNotice(null)
    setWidgetOpen(false)
    setWidgetLogs([])
    setCurrentStepIndex(0)
    setActiveAgentName('')
    setIsFinished(false)
    setProgressEvents([])
    setRunStatus('idle')
    setWidgetError(null)
    if (fileRef.current) fileRef.current.value = ''
    if (audioFileRef.current) audioFileRef.current.value = ''
  }

  return (
    <div className="app-shell">
      {/* Floating Gemini-style Agent Transparency Working Drawer */}
      <AgentWorkingWidget
        isOpen={widgetOpen}
        events={progressEvents}
        runStatus={runStatus}
        error={widgetError}
        disconnected={progressDisconnected}
        onComplete={() => {
          setWidgetOpen(false)
          setChatOpen(false)
        }}
        onOpen={() => setWidgetOpen(true)}
        onChat={() => { setWidgetOpen(false); setChatOpen(true) }}
      />
      {!chatOpen && progressEvents.length > 0 && (
        <button className="resume-chat-launcher" onClick={() => setChatOpen(true)} title="Open Resume Agent" aria-label="Open Resume Agent">
          <img src="/icon.png" alt="" />
          <span>Chat</span>
        </button>
      )}
      
      {chatOpen && (
        <ResumeChatPanel
          profile={profile}
          workflow={workflow}
          input={chatInput}
          setInput={setChatInput}
          messages={chatMessages}
          setMessages={setChatMessages}
          onClose={() => setChatOpen(false)}
        />
      )}
      <header className="app-navbar">
        <div className="navbar-brand">
          <img src="/icon.png" alt="Pathwise Icon" className="brand-logo-img" />
          <strong>pathwise</strong>
        </div>

        <div className="nav-actions">
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
              <button className={mode === 'voice' ? 'selected' : ''} onClick={() => setMode('voice')}>🎙 Voice</button>
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
            ) : mode === 'text' ? (
              <textarea
                className="resume-textarea"
                value={text}
                onChange={(event) => setText(event.target.value)}
                placeholder="Paste the full text of your resume here..."
              />
            ) : (
              <div className="voice-panel">
                {/* Mic button */}
                <button
                  className={`voice-mic-btn ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`}
                  onClick={toggleVoiceRecording}
                  disabled={isTranscribing}
                  title={isRecording ? 'Stop & transcribe' : isTranscribing ? 'Transcribing…' : 'Start recording'}
                >
                  {isTranscribing ? (
                    <>
                      <span className="voice-mic-icon">⏳</span>
                      <span>Transcribing…</span>
                    </>
                  ) : isRecording ? (
                    <>
                      <span className="voice-mic-icon">⏹</span>
                      <span>Stop & Transcribe</span>
                      <span className="voice-wave">
                        <span /><span /><span /><span /><span />
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="voice-mic-icon">🎙</span>
                      <span>Start Recording</span>
                    </>
                  )}
                </button>

                {/* Status hint */}
                <p className="voice-hint">
                  {isTranscribing
                    ? 'Sending audio to Gemini AI for transcription…'
                    : isRecording
                    ? 'Listening… speak clearly. Click ⏹ when done.'
                    : voiceTranscript
                    ? 'Recording saved. Record more or click Analyze Resume ⚡'
                    : 'Click the mic to speak your resume details aloud.'}
                </p>

                {/* Live interim preview while recording */}
                {isRecording && liveInterim && (
                  <div className="voice-interim">
                    <span className="voice-interim-dot" />
                    <em>{liveInterim}</em>
                  </div>
                )}

                {/* Transcribing spinner bar */}
                {isTranscribing && (
                  <div className="voice-transcribing-bar">
                    <div className="voice-transcribing-fill" />
                  </div>
                )}

                {/* ── Divider + MP3 / audio file upload ──────────────── */}
                {!isRecording && !isTranscribing && (
                  <div className="voice-or-divider">
                    <span>or upload an audio file</span>
                  </div>
                )}

                {!isRecording && !isTranscribing && (
                  <label className="voice-file-dropzone">
                    <input
                      ref={audioFileRef}
                      type="file"
                      accept=".mp3,.wav,.ogg,.webm,.m4a,audio/*"
                      onChange={handleAudioFileUpload}
                    />
                    <span className="voice-file-icon">🎵</span>
                    <span className="voice-file-text">Drop MP3 / audio file here</span>
                    <span className="voice-file-sub">MP3, WAV, OGG, M4A · up to 25 MB</span>
                  </label>
                )}

                {/* Final transcript — editable so user can correct it */}
                {voiceTranscript && !isRecording && (
                  <div className="voice-transcript">
                    <div className="voice-transcript-label">✏️ click to edit</div>
                    <textarea
                      className="voice-transcript-textarea"
                      value={voiceTranscript}
                      onChange={(e) => setVoiceTranscript(e.target.value)}
                      rows={5}
                    />
                    <div className="voice-transcript-actions">
                      <button
                        className="quiet-button"
                        onClick={() => setVoiceTranscript('')}
                      >
                        ✕ Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {profile ? (
              <div className="profile-snapshot-wrap">
                <ProfileSnapshot profile={profile} />
                <button className="ghost-button full-width margin-top-sm" onClick={rerunCareerAnalysis}>
                  🔄 Refresh Analysis
                </button>
              </div>
            ) : (
              <div className="empty-snapshot">Extracted profile details will appear here.</div>
            )}
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

            <label className="check-control">
              <input
                type="checkbox"
                checked={freeOnly}
                onChange={(event) => setFreeOnly(event.target.checked)}
              />
              <span>Free courses only</span>
            </label>

            <button className="accent-button full-width analyze-right-button" onClick={runFullAgentPipeline}>
              Analyze Resume <span>⚡</span>
            </button>
          </div>
        </section>

        {notice && (
          <div className={`notice ${notice.type} ${notice.type === 'info' ? 'notice-toast' : ''}`} role="status">
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
            freeOnly={workflow.free_only ?? freeOnly}
            careerSimulator={careerSimulator}
            simulatorInput={simulatorInput}
            setSimulatorInput={setSimulatorInput}
            runCareerSimulator={runCareerSimulator}
            simulatorBusy={simulatorBusy}
            setNotice={setNotice}
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

function ResumeChatPanel({ profile, workflow, input, setInput, messages, setMessages, onClose }) {
  const [sending, setSending] = React.useState(false)

  async function sendMessage(event) {
    event.preventDefault()
    const question = input.trim()
    if (!question || sending) return
    const nextMessages = [...messages, { role: 'user', text: question }]
    setMessages(nextMessages)
    setInput('')
    setSending(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/profile/resume-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: question,
          profile: profile || {},
          workflow: workflow || {},
          history: messages.slice(-8).map(({ role, text }) => ({ role, text })),
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Resume assistant is unavailable.')
      setMessages((current) => [...current, { role: 'assistant', text: data.reply }])
    } catch (error) {
      setMessages((current) => [...current, { role: 'assistant', text: error.message }])
    } finally {
      setSending(false)
    }
  }

  return (
    <aside className="resume-chat-panel">
      <div className="resume-chat-header">
        <div className="resume-chat-identity">
            <div className="resume-chat-avatar"><img src="/agenticon.png" alt="" /></div>
          <div><strong>Resume Guide</strong><span>Grounded in your analysis</span></div>
        </div>
        <button className="resume-chat-close" onClick={onClose} aria-label="Close resume chat">×</button>
      </div>
      <div className="resume-chat-body">
        <div className="resume-chat-message assistant">{workflow ? 'Your analysis is ready. Ask me about your resume, matched roles, skill gaps, or learning paths.' : profile ? 'I have your resume profile. Ask me anything while the rest of the analysis continues.' : 'I’m processing your uploaded resume. Chat will be available as soon as the profile is extracted.'}</div>
        {messages.map((message, index) => <div className={`resume-chat-message ${message.role}`} key={`${message.role}-${index}`}>{message.text}</div>)}
      </div>
      <form className="resume-chat-compose" onSubmit={sendMessage}>
        <input value={input} onChange={(event) => setInput(event.target.value)} disabled={!profile || sending} placeholder={profile ? 'Ask about your resume...' : 'Extracting resume profile...'} aria-label="Ask about your resume" />
        <button type="submit" disabled={sending} aria-label="Send question">{sending ? '…' : '↑'}</button>
      </form>
    </aside>
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

function ResultsDashboard({ profile, targetRole, location, workflow, matchedJobs, gaps, opportunities, courses, currentJobs, missingSkills, freeOnly, careerSimulator, simulatorInput, setSimulatorInput, runCareerSimulator, simulatorBusy, setNotice }) {
  const timeToReady = workflow?.time_to_ready || {}
  const opportunityDiscovery = workflow?.opportunity_discovery || workflow?.opportunity_analysis?.opportunity_discovery || {
    current_matching_jobs: workflow?.current_jobs ?? workflow?.opportunity_analysis?.current_jobs ?? 0,
    skill_opportunities: [],
    recommended_sequence: [],
    cumulative_plan: [],
    total_jobs_unlocked: 0,
    total_learning_weeks: 0,
    total_cost_inr: 0,
  }
  const retrievedJobs = workflow?.retrieved_jobs || []
  const retrievedCourses = workflow?.retrieved_courses || []
  const retrievedSources = workflow?.retrieved_sources || []
  const aiReasoning = workflow?.ai_reasoning || []
  const careerIntelligence = workflow?.career_intelligence || {}
  const sourceById = Object.fromEntries(retrievedSources.map((source) => [source.source_id, source]))
  const jobsById = Object.fromEntries((workflow?.jobs || []).map((job) => [job.job_id, job]))
  return (
    <section className="results-area">
      <div className="results-header">
        <div>
          <p className="kicker">Multi-Agent Workflow Results</p>
          <h2>Here is what your resume means</h2>
        </div>
        <span className="source-pill">
          Demo job database
          <span className="online-dot" />
        </span>
        {freeOnly && <span className="source-pill free-filter-pill">Free courses only</span>}
      </div>

      <div className="metrics-row">
        <Metric label="Jobs that fit now" value={currentJobs} note="Your starting point" accent />
        <Metric label="Jobs checked" value={matchedJobs.length} note="Vector matched directions" />
        <Metric label="Skills to strengthen" value={missingSkills.length} note="Target learning list" />
        <Metric label="Courses suggested" value={courses.length} note="Curated next steps" />
      </div>

      <section className="career-intelligence-section">
        <SectionTitle number="I" title="Career Intelligence" meta="Deterministic analysis" />
        <div className="career-charts-grid">
          <SkillGapChart data={careerIntelligence.skill_gap || []} />
          <OpportunityUnlockChart data={careerIntelligence.opportunity_unlock || []} />
          <SkillCoverageChart data={careerIntelligence.skill_coverage} />
        </div>
      </section>

      <section className="evidence-section">
        <SectionTitle number="R" title="Evidence from PathWise Knowledge Base" meta={workflow.rag_available ? 'FAISS RAG Retrieval' : 'RAG unavailable'} />
        <div className="evidence-summary-grid">
          <div>
            <strong>{retrievedJobs.length}</strong>
            <span>jobs retrieved</span>
          </div>
          <div>
            <strong>{retrievedCourses.length}</strong>
            <span>courses retrieved</span>
          </div>
        </div>
        <div className="evidence-group">
          <span>Jobs</span>
          <SourceChips sourceIds={retrievedJobs.map((source) => source.source_id)} sourceById={sourceById} />
        </div>
        <div className="evidence-group">
          <span>Courses</span>
          <SourceChips sourceIds={retrievedCourses.map((source) => source.source_id)} sourceById={sourceById} />
        </div>
      </section>

      <div className="results-grid">
        <section className="result-section">
          <SectionTitle number="A" title="Jobs that fit you" meta="Top Market Matches" />
          <p className="plain-helper">These are the roles closest to your current experience & skills vector.</p>
          <div className="job-list">
            {matchedJobs.slice(0, 6).map((job) => (
              <JobCard
                job={job}
                jobDetails={jobsById[job.job_id] || {}}
                readiness={timeToReady[job.job_id]}
                evidence={sourceById[job.job_id]}
                key={job.job_id || job.title}
              />
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

      <SkillCombinationOptimizer
        profile={{
          ...(profile || {}),
          skills: profile?.skills || [],
          target_role: targetRole,
          location,
        }}
      />

      <section className="opportunity-section">
        <SectionTitle title="Your learning path" meta="PathWise discovery engine" />
        <p className="plain-helper">Your recommended sequence of skills to strengthen next.</p>
        <div className="direct-learning-path">
          {(opportunityDiscovery.recommended_sequence || []).slice(0, 5).map((skill, index) => (
            <span className="direct-learning-step" key={`${skill}-${index}`}><b>{index + 1}</b>{skill}</span>
          ))}
          {!opportunityDiscovery.recommended_sequence?.length && <EmptyState text="No learning path is available for this profile yet." />}
        </div>
      </section>

      <section className="learning-section">
        <SectionTitle number="G" title="Your training plan" meta="High-ROI Recommended Courses" />
        <p className="plain-helper">These course recommendations are chosen by the Training Agent to close your top skill gaps.</p>
        <div className="course-grid">
          {courses.map((course) => (
            <CourseCard course={course} sourceById={sourceById} key={course.course_name || course.course_id} />
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
            onClick={() => {
              setNotice({ type: 'info', text: 'Your report is being created. This may take a minute.' })
              setTimeout(() => generatePdfReport({ profile, workflow, targetRole, location }), 100)
            }}
          >
            📥 Download Report (PDF)
          </button>
        </div>
      </section>
    </section>
  )
}

function ToolActivity({ trace }) {
  const [open, setOpen] = React.useState(false)
  return (
    <section className="tool-activity-section">
      <button className="tool-activity-toggle" type="button" onClick={() => setOpen((value) => !value)}>
        <span>Agent Tools Used</span><span>{open ? '⌃' : '⌄'}</span>
      </button>
      {open && (
        <div className="tool-activity-list">
          {trace.length ? trace.map((entry, index) => (
            <article className="tool-activity-row" key={`${entry.tool_name}-${index}`}>
              <div><strong>{entry.tool_name}</strong><span className={entry.status === 'success' ? 'tool-success' : 'tool-error'}>{entry.status === 'success' ? '✓ Success' : '⚠ Error'}</span></div>
              {Object.keys(entry.arguments || {}).length > 0 && <code>{JSON.stringify(entry.arguments)}</code>}
              <span>{entry.result_summary || 'No result summary'}</span>
            </article>
          )) : <span className="tool-empty">No tools were requested during this run; the existing deterministic state was sufficient.</span>}
        </div>
      )}
    </section>
  )
}

function SkillCombinationOptimizer({ profile }) {
  const [maxWeeks, setMaxWeeks] = React.useState(4)
  const [budgetInr, setBudgetInr] = React.useState(1000)
  const [result, setResult] = React.useState(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState('')
  const [expanded, setExpanded] = React.useState(null)

  async function runOptimizer() {
    setLoading(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE_URL}/api/skill-combination-optimizer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_profile: profile, max_weeks: Number(maxWeeks), budget_inr: Number(budgetInr) }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Unable to optimize skill combinations.')
      setResult(data)
      setExpanded(null)
    } catch (requestError) {
      setError(requestError.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  const renderCard = (item, index, exceeded = false) => {
    const isOpen = expanded === `${exceeded ? 'x' : 'v'}-${index}`
    const limitText = !item.within_time && !item.within_budget
      ? 'Exceeds time and budget'
      : !item.within_time ? `Exceeds ${result.constraints.max_weeks} week limit`
        : `Exceeds ₹${Number(result.constraints.budget_inr).toLocaleString('en-IN')} budget`
    return (
      <article className={`optimizer-card ${exceeded ? 'exceeded' : ''}`} key={`${item.skills.join('-')}-${index}`}>
        <div className="optimizer-card-topline">
          <div>
            <strong>{item.skills.join(' + ')}</strong>
            <span>{exceeded ? `⚠ ${limitText}` : '✓ Within your limits'}</span>
          </div>
          <b>+{item.additional_jobs}</b>
        </div>
        <div className="optimizer-metrics">
          <span><strong>{item.additional_jobs}</strong> opportunities</span>
          <span><strong>{formatWeeks(item.learning_weeks)}</strong> weeks</span>
          <span><strong>{formatInr(item.cost_inr)}</strong></span>
        </div>
        <div className="optimizer-actions">
          <button className="plan-toggle" type="button" onClick={() => setExpanded(isOpen ? null : `${exceeded ? 'x' : 'v'}-${index}`)}>
            {isOpen ? 'Hide details' : 'View skills & plan'}
          </button>
          {item.job_ids?.length > 0 && <span>{item.job_ids.length} unlocked jobs</span>}
        </div>
        {isOpen && (
          <div className="optimizer-details">
            <div><b>Skills</b><span>{item.skills.join(' · ')}</span></div>
            <div><b>Learning plan</b>
              {item.courses?.length ? item.courses.map((course) => (
                <span key={course.course_id}>{course.title} · {formatWeeks(course.duration_weeks)} weeks · {course.is_free ? 'Free' : formatInr(course.price_inr)}</span>
              )) : <span>No course covers this combination in the catalog.</span>}
            </div>
            {item.unlocked_jobs?.length > 0 && <div><b>Unlocked jobs</b>
              {item.unlocked_jobs.slice(0, 8).map((job) => <span key={job.job_id}>{job.title} · {job.company || 'Company undisclosed'} · {job.location || 'Location unknown'}</span>)}
            </div>}
          </div>
        )}
      </article>
    )
  }

  return (
    <section className="optimizer-section">
      <SectionTitle number="O" title="Skill Combination Optimizer" meta="Deterministic What-If Analysis" />
      <p className="plain-helper">Find which combination of two or three supported skills unlocks the most additional opportunities within your limits.</p>
      <div className="optimizer-controls">
        <label>Maximum learning time <input type="number" min="0" step="0.5" value={maxWeeks} onChange={(event) => setMaxWeeks(event.target.value)} /> <span>weeks</span></label>
        <label>Learning budget <input type="number" min="0" step="100" value={budgetInr} onChange={(event) => setBudgetInr(event.target.value)} /> <span>INR</span></label>
        <button className="accent-button" type="button" onClick={runOptimizer} disabled={loading}>{loading ? 'Evaluating...' : 'Find Best Skill Combination'}</button>
      </div>
      {error && <div className="notice error">{error}</div>}
      {result && (
        <>
          <div className="optimizer-summary">Evaluated {result.combinations.length} data-backed combinations from {result.candidate_skills.length} supported skills.</div>
          <div className="optimizer-group">
            <h4>Within Your Limits</h4>
            {result.valid_combinations.length ? result.valid_combinations.slice(0, 8).map((item, index) => renderCard(item, index)) : <EmptyState text={`No combination fits within ${result.constraints.max_weeks} weeks and ${formatInr(result.constraints.budget_inr)}.`} />}
          </div>
          <div className="optimizer-group">
            <h4>Beyond Your Limits</h4>
            {result.constraint_exceeded_combinations.length ? result.constraint_exceeded_combinations.slice(0, 8).map((item, index) => renderCard(item, index, true)) : <EmptyState text="No combinations exceeded your current limits." />}
          </div>
        </>
      )}
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

function SourceChips({ sourceIds, sourceById }) {
  const uniqueIds = [...new Set((sourceIds || []).filter(Boolean))]
  if (!uniqueIds.length) return <span className="no-sources">No retrieved sources</span>
  return (
    <div className="source-chip-row">
      {uniqueIds.map((sourceId) => {
        const source = sourceById?.[sourceId] || {}
        const url = source.url || source.metadata?.url
        const chip = <span className="source-chip">{sourceId}</span>
        return url ? (
          <a href={url} target="_blank" rel="noreferrer" className="source-chip-link" key={sourceId}>{chip}</a>
        ) : (
          <span key={sourceId}>{chip}</span>
        )
      })}
    </div>
  )
}

function textFromFocusItem(item) {
  if (typeof item === 'string') return item
  return item?.topic || item?.skill || item?.course || ''
}

function gapSkill(item) {
  if (typeof item === 'string') return item
  return item?.skill || 'Priority gap'
}

function gapReason(item) {
  if (typeof item === 'string') return 'Priority skill gap identified by the analysis.'
  return item?.reason || 'Priority skill gap identified by the analysis.'
}

function AiRecommendationCard({ reasoning, sourceById }) {
  const priorityGaps = reasoning?.priority_gaps || []
  const learningFocus = reasoning?.learning_focus || []
  return (
    <article className="ai-recommendation-card">
      <div className="ai-card-topline">
        <span>AI Recommendation</span>
        <b>{reasoning?.source === 'gemini' ? 'Gemini' : 'Fallback'}</b>
      </div>
      <p>{reasoning?.summary || 'No summary returned for this recommendation.'}</p>

      {priorityGaps.slice(0, 3).map((gap) => (
        <div className="ai-evidence-item" key={`${gapSkill(gap)}-${gapReason(gap)}`}>
          <strong>{gapSkill(gap)}</strong>
          <span>{gapReason(gap)}</span>
          <SourceChips sourceIds={(typeof gap === 'object' && gap?.source_ids) || reasoning.source_ids || []} sourceById={sourceById} />
        </div>
      ))}

      {learningFocus.length > 0 && (
        <div className="ai-learning-focus">
          <span>Learning focus</span>
          {learningFocus.slice(0, 3).map((item) => (
            <div className="ai-focus-row" key={textFromFocusItem(item) || 'focus'}>
              <strong>{textFromFocusItem(item) || 'Learning goal'}</strong>
              <SourceChips sourceIds={(typeof item === 'object' && item?.source_ids) || []} sourceById={sourceById} />
            </div>
          ))}
        </div>
      )}
    </article>
  )
}

function formatInr(value) {
  const amount = Number(value || 0)
  return `₹${amount.toLocaleString('en-IN')}`
}

function formatWeeks(value) {
  const weeks = Number(value || 0)
  return Number.isInteger(weeks) ? String(weeks) : weeks.toFixed(1)
}

function JobCard({ job, jobDetails, readiness, evidence }) {
  const score = Math.round(job.match_score || 0)
  const [detailsOpen, setDetailsOpen] = React.useState(false)
  const [planOpen, setPlanOpen] = React.useState(false)
  const courses = readiness?.recommended_courses || []
  const uncovered = readiness?.uncovered_skills || []
  const matchedSkills = job.matched_skills || []
  const missingSkills = job.missing_skills || job.unmatched_skills || []
  const requiredSkills = jobDetails.required_skills || [...matchedSkills, ...missingSkills]
  const jobUrl = job.url || job.job_url || jobDetails.job_url || ''
  const readyNow = readiness?.is_fully_covered && Number(readiness?.total_weeks || 0) === 0
  const readyText = readyNow ? 'Ready now' : readiness ? `${formatWeeks(readiness.total_weeks)} weeks` : 'Learning plan unavailable'

  return (
    <article className="job-card">
      <div className="job-card-header">
        <div className="job-card-title">
          <strong>{job.title || job.job_title || 'Untitled role'}</strong>
          <span>{job.company || jobDetails.company || 'Company undisclosed'} · {job.location || jobDetails.location || 'Location unknown'}</span>
        </div>
        <div className="job-match-score"><b>{score}</b><small>% match</small></div>
      </div>

      <div className="job-skill-groups">
        <div><span className="job-skill-label matched">✓ Matched skills</span><div className="job-skill-chips">{matchedSkills.length ? matchedSkills.map((skill) => <span className="job-skill-chip matched" key={`matched-${skill}`}>{skill}</span>) : <span className="job-card-muted">None detected</span>}</div></div>
        <div><span className="job-skill-label missing">⚠ Missing skills</span><div className="job-skill-chips">{missingSkills.length ? missingSkills.map((skill) => <span className="job-skill-chip missing" key={`missing-${skill}`}>{skill}</span>) : <span className="job-card-muted">No skill gaps</span>}</div></div>
      </div>

      <div className="job-coverage"><div><span>Skill coverage</span><b>{score}%</b></div><div className="job-coverage-track"><div style={{ width: `${Math.min(100, Math.max(0, score))}%` }} /></div></div>

      <div className="job-readiness-summary">
        <span><b>{readyNow ? '✓ Ready now' : 'Time to Ready'}</b>{!readyNow && `: ${readyText}`}</span>
        <span><b>Cost:</b> {readiness ? formatInr(readiness.total_cost_inr) : 'Unavailable'}</span>
        {missingSkills.length > 0 && <span className="warning-text">{missingSkills.length} skill{missingSkills.length === 1 ? '' : 's'} to learn</span>}
      </div>

      <div className="job-card-actions">
        {jobUrl ? <a className="job-card-button primary" href={jobUrl} target="_blank" rel="noreferrer">View Job ↗</a> : <span className="job-card-button disabled">Job link unavailable</span>}
        <button className="job-card-button" type="button" onClick={() => setPlanOpen((value) => !value)} disabled={!readiness}>{planOpen ? 'Hide Learning Plan' : 'Learning Plan'}</button>
        <button className="job-card-button" type="button" onClick={() => setDetailsOpen((value) => !value)}>{detailsOpen ? 'Hide Details' : 'Details'}</button>
      </div>

      {planOpen && readiness && <div className="job-card-panel learning-plan-panel">
        <div className="job-panel-heading"><strong>Learning Plan</strong><span>{formatWeeks(readiness.total_weeks)} weeks · {formatInr(readiness.total_cost_inr)}</span></div>
        {courses.map((course) => <div className="job-course-row" key={course.course_id}><div><strong>{(course.skills_covered || []).join(', ') || course.title}</strong><span>{course.title} · {course.provider || 'Course catalog'}</span></div><span>{formatWeeks(course.duration_weeks)} weeks · {course.is_free ? 'Free' : formatInr(course.price_inr)} {course.url && <a href={course.url} target="_blank" rel="noreferrer">View Course ↗</a>}</span></div>)}
        {uncovered.map((skill) => <div className="job-course-row warning" key={skill}><strong>{skill}</strong><span>Learning plan unavailable</span></div>)}
        {!courses.length && !uncovered.length && <span className="job-card-muted">Already ready for this role.</span>}
      </div>}

      {detailsOpen && <div className="job-card-panel job-details-panel">
        <div><h4>Required Skills</h4><div className="required-skill-list">{requiredSkills.map((skill) => { const isMatched = matchedSkills.some((item) => String(item || '').toLowerCase() === String(skill || '').toLowerCase()); return <span className={isMatched ? 'required-skill matched' : 'required-skill missing'} key={skill}>{isMatched ? '✓' : '✕'} {skill}</span> })}</div></div>
        <div><h4>Why you're missing</h4>{missingSkills.length ? missingSkills.map((skill) => <div className="missing-reason" key={skill}><strong>{skill}</strong><span>Required by this role{jobDetails.description ? ` — listed in the job requirements for ${job.title || 'this position'}.` : '.'}</span></div>) : <span className="job-card-muted">No missing skills identified.</span>}</div>
        {evidence && <div><h4>Evidence</h4><SourceChips sourceIds={[evidence.source_id]} sourceById={{ [evidence.source_id]: evidence }} /></div>}
        <div><h4>Recommended Learning</h4>{courses.length ? courses.map((course) => <div className="job-recommendation" key={`recommend-${course.course_id}`}><strong>{(course.skills_covered || []).join(', ') || course.title}</strong><span>{course.title} · {formatWeeks(course.duration_weeks)} weeks · {course.is_free ? 'Free' : formatInr(course.price_inr)}</span></div>) : <span className="job-card-muted">Learning plan unavailable for the current course catalog.</span>}</div>
      </div>}
    </article>
  )
}

// Kept temporarily for compatibility with any external imports; the dashboard
// uses JobCard above for all matched-job rendering.
function LegacyJobRow({ job, readiness }) {
  const score = Math.round(job.match_score || 0)
  const [expanded, setExpanded] = React.useState(false)
  const courses = readiness?.recommended_courses || []
  const uncovered = readiness?.uncovered_skills || []
  const readyText = readiness
    ? (readiness.total_weeks === 0 && readiness.is_fully_covered ? 'Already ready' : `${formatWeeks(readiness.total_weeks)} weeks`)
    : 'Not calculated'
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
        {readiness && (
          <div className="readiness-panel">
            <div className="readiness-summary">
              <span><b>Time to Ready:</b> {readyText}</span>
              <span><b>Cost to Ready:</b> {formatInr(readiness.total_cost_inr)}</span>
              {!readiness.is_fully_covered && <span className="warning-text">Uncovered: {uncovered.join(', ')}</span>}
            </div>
            {(courses.length > 0 || uncovered.length > 0) && (
              <button className="plan-toggle" type="button" onClick={() => setExpanded((value) => !value)}>
                {expanded ? 'Hide Learning Plan' : 'View Learning Plan'}
              </button>
            )}
            {expanded && (
              <div className="learning-plan">
                {courses.map((course) => (
                  <div className="learning-plan-row" key={course.course_id}>
                    <div>
                      <strong>{course.title}</strong>
                      <span>{course.provider || 'Course catalog'} · {(course.skills_covered || []).join(', ')}</span>
                    </div>
                    <span>{formatWeeks(course.duration_weeks)} weeks · {course.is_free ? 'Free' : formatInr(course.price_inr)}</span>
                  </div>
                ))}
                {uncovered.map((skill) => (
                  <div className="learning-plan-row warning" key={skill}>
                    <div>
                      <strong>{skill}</strong>
                      <span>No matching course in the current catalog</span>
                    </div>
                    <span>Uncovered</span>
                  </div>
                ))}
                <div className="learning-plan-total">
                  Total: {formatWeeks(readiness.total_weeks)} weeks · {formatInr(readiness.total_cost_inr)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

function CourseCard({ course, sourceById }) {
  return (
    <article className="course-card">
      <div className="course-topline">
        <span>Recommended course</span>
        <b>{course.learning_impact ?? '—'} impact</b>
      </div>
      <h3>{course.course_name || course.title}</h3>
      <p>{course.provider || 'Course catalog'} · {course.duration_weeks || '—'} weeks</p>
      <div className="course-stats">
        <strong>+{course.jobs_unlocked || 0}</strong>
        <span>jobs unlocked</span>
      </div>
      {course.reasoning && <blockquote>{course.reasoning}</blockquote>}
      <SourceChips sourceIds={course.source_ids || []} sourceById={sourceById} />
      {course.url && <a href={course.url} target="_blank" rel="noreferrer">View resource ↗</a>}
    </article>
  )
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('UI Render Error caught by ErrorBoundary:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '40px', maxWidth: '700px', margin: '60px auto', background: '#ffffff', borderRadius: '16px', border: '1px solid #fee2e2', boxShadow: '0 20px 40px rgba(15,23,42,0.1)', textAlign: 'center', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
          <div style={{ fontSize: '40px', marginBottom: '16px' }}>⚠️</div>
          <h2 style={{ color: '#0f172a', fontSize: '20px', fontWeight: '700', marginBottom: '8px' }}>Interface Encountered an Issue</h2>
          <p style={{ color: '#64748b', fontSize: '14px', marginBottom: '20px', lineHeight: '1.5' }}>
            {this.state.error?.message || 'An unexpected rendering error occurred.'}
          </p>
          <button
            style={{ padding: '10px 22px', background: 'linear-gradient(135deg, #4f46e5, #4338ca)', color: '#ffffff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '600', fontSize: '14px' }}
            onClick={() => {
              this.setState({ hasError: false, error: null })
              window.location.reload()
            }}
          >
            Reload Application
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
)
