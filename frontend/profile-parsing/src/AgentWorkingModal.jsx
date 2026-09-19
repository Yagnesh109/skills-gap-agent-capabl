import React, { useState, useEffect } from 'react'

export function AgentWorkingModal({ isOpen, mode, currentStepIndex, logs, onComplete, isFinished, error }) {
  const [elapsed, setElapsed] = useState(0)
  const [showLogs, setShowLogs] = useState(true)

  useEffect(() => {
    let timer
    if (isOpen && !isFinished) {
      setElapsed(0)
      timer = setInterval(() => {
        setElapsed((prev) => prev + 1)
      }, 1000)
    }
    return () => clearInterval(timer)
  }, [isOpen, isFinished])

  if (!isOpen) return null

  const parseSteps = [
    {
      id: 'file_read',
      agent: 'Document Extractor Agent',
      icon: '📄',
      title: 'Reading Document Stream',
      description: 'Extracting text structure, formatting, and raw resume tokens',
    },
    {
      id: 'gemini_vision',
      agent: 'Profile Parsing Agent (Gemini 3.6)',
      icon: '🤖',
      title: 'Structuring Candidate Profile',
      description: 'Identifying skills, work history, target roles & education using Gemini AI',
    },
    {
      id: 'profile_ready',
      agent: 'Validation Agent',
      icon: '✅',
      title: 'Validating Profile Schema',
      description: 'Structuring normalized JSON profile payload for down-stream workflows',
    }
  ]

  const analysisSteps = [
    {
      id: 'profile_sync',
      agent: 'Profile Parsing Agent',
      icon: '👤',
      title: 'Context Sync & Role Intent',
      description: 'Loading target career role, location preference, and skill matrix',
    },
    {
      id: 'market_match',
      agent: 'Skill Match Agent',
      icon: '🔍',
      title: 'Live Market Job Search',
      description: 'Searching Jooble & vector embeddings for candidate role alignment',
    },
    {
      id: 'gap_graph',
      agent: 'Gap Analysis Agent (LangGraph)',
      icon: '⚡',
      title: 'LangGraph Gap Reasoning',
      description: 'Evaluating candidate skills vs job market requirements to calculate readiness',
    },
    {
      id: 'opportunity',
      agent: 'Opportunity Graph Agent',
      icon: '📈',
      title: 'Opportunity & ROI Analysis',
      description: 'Simulating skill unlock impact and job availability multiplication',
    },
    {
      id: 'training',
      agent: 'Training Agent (MCP)',
      icon: '🎓',
      title: 'High-ROI Course Pathways',
      description: 'Mapping missing skills to curated training courses and execution plans',
    }
  ]

  const activeSteps = mode === 'parse' ? parseSteps : analysisSteps
  const totalSteps = activeSteps.length
  const progressPercent = isFinished
    ? 100
    : Math.min(100, Math.round(((currentStepIndex + 1) / totalSteps) * 90))

  return (
    <div className="agent-overlay-backdrop">
      <div className="agent-modal-card">
        {/* Header Header */}
        <div className="agent-modal-header">
          <div className="agent-title-lockup">
            <div className={`agent-status-badge ${isFinished ? 'done' : error ? 'error' : 'live'}`}>
              <span className="pulse-dot" />
              {isFinished ? 'Execution Complete' : error ? 'Task Failed' : 'Agent Live Execution'}
            </div>
            <h2>
              {mode === 'parse' ? 'Profile Extraction Pipeline' : 'Multi-Agent Career Path Workflow'}
            </h2>
            <p className="agent-modal-subtitle">
              {mode === 'parse'
                ? 'Processing document with Gemini 3.6 AI Vision'
                : 'LangGraph multi-agent cluster executing real-time career matching'}
            </p>
          </div>

          <div className="agent-timer-badge">
            <span className="timer-icon">⏱️</span>
            <span>{elapsed}s elapsed</span>
          </div>
        </div>

        {/* Global Progress Rail */}
        <div className="agent-progress-rail">
          <div
            className="agent-progress-bar"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Multi-Agent Node Pipeline */}
        <div className="agent-pipeline-grid">
          {activeSteps.map((step, idx) => {
            const isDone = isFinished || idx < currentStepIndex
            const isCurrent = !isFinished && idx === currentStepIndex
            const isPending = !isFinished && idx > currentStepIndex

            return (
              <div
                key={step.id}
                className={`agent-node-card ${
                  isDone ? 'node-done' : isCurrent ? 'node-active' : 'node-pending'
                }`}
              >
                <div className="node-icon-wrapper">
                  <span className="node-icon">{step.icon}</span>
                  {isDone && <span className="node-check">✓</span>}
                  {isCurrent && <span className="node-spinner" />}
                </div>

                <div className="node-content">
                  <div className="node-agent-name">{step.agent}</div>
                  <h4 className="node-title">{step.title}</h4>
                  <p className="node-desc">{step.description}</p>
                </div>

                <div className="node-status-pill">
                  {isDone ? 'COMPLETED' : isCurrent ? 'EXECUTING' : 'WAITING'}
                </div>
              </div>
            )
          })}
        </div>

        {/* Live Internal Log Terminal Stream */}
        <div className="agent-terminal-section">
          <div className="terminal-header">
            <div className="terminal-title">
              <span className="terminal-dot red" />
              <span className="terminal-dot yellow" />
              <span className="terminal-dot green" />
              <span className="terminal-label">Internal Working Logs & Thought Trace</span>
            </div>
            <button
              className="terminal-toggle-btn"
              onClick={() => setShowLogs(!showLogs)}
            >
              {showLogs ? 'Hide Logs ▲' : 'Show Logs ▼'}
            </button>
          </div>

          {showLogs && (
            <div className="terminal-body">
              {logs.length === 0 ? (
                <div className="terminal-line dim">Initializing multi-agent graph state...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`terminal-line ${log.type || 'info'}`}>
                    <span className="log-time">[{log.time || '00:00'}]</span>
                    <span className="log-agent">{log.agent}:</span>
                    <span className="log-msg">{log.message}</span>
                  </div>
                ))
              )}
              {isFinished && (
                <div className="terminal-line success font-bold">
                  [DONE] All multi-agent node tasks executed successfully.
                </div>
              )}
              {error && (
                <div className="terminal-line error font-bold">
                  [ERROR] {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Bottom Actions */}
        <div className="agent-modal-footer">
          {isFinished ? (
            <button className="accent-button full-width animate-bounce-subtle" onClick={onComplete}>
              View Results Dashboard <span>→</span>
            </button>
          ) : error ? (
            <button className="quiet-button full-width" onClick={onComplete}>
              Close & Retry
            </button>
          ) : (
            <div className="running-hint">
              <span className="glowing-orb" />
              <span>Agents are currently working transparently. Please stand by...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
