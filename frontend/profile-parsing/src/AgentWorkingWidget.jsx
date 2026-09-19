import React, { useState, useEffect, useRef } from 'react'

export function AgentWorkingWidget({ isOpen, currentStepIndex, activeAgentName, logs, isFinished, error, onComplete }) {
  const [elapsed, setElapsed] = useState(0)
  const [isMinimized, setIsMinimized] = useState(false)
  const [isExpandedLogs, setIsExpandedLogs] = useState(true)
  const logsEndRef = useRef(null)

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

  useEffect(() => {
    if (logsEndRef.current && isExpandedLogs) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, isExpandedLogs])

  if (!isOpen) return null

  const pipelineSteps = [
    { name: 'Document Reader', agent: 'Document Extractor Agent', icon: '📄' },
    { name: 'Gemini 3.6 AI', agent: 'Profile Extractor Agent (Gemini 3.6)', icon: '🤖' },
    { name: 'Jooble Matcher', agent: 'Skill Match Agent (Jooble & Vector DB)', icon: '🔍' },
    { name: 'LangGraph Engine', agent: 'Gap Analysis Agent (LangGraph)', icon: '⚡' },
    { name: 'Opportunity Graph', agent: 'Opportunity Simulation Agent', icon: '📈' },
    { name: 'Training MCP', agent: 'Training Recommendation Agent (MCP)', icon: '🎓' },
    { name: 'Report Generator', agent: 'Report Generation Agent', icon: '📝' },
  ]

  const totalSteps = pipelineSteps.length
  const progressPercent = isFinished
    ? 100
    : Math.min(100, Math.round(((currentStepIndex + 1) / totalSteps) * 90))

  const latestLog = logs.length > 0 ? logs[logs.length - 1] : null
  const currentStepInfo = pipelineSteps[currentStepIndex] || pipelineSteps[0]

  return (
    <>
      {/* Subtle, non-blocking background screen fade */}
      <div className={`agent-backdrop-fade ${isFinished ? 'fading-out' : ''}`} />

      {/* Floating Live Agent Working Transparency Widget */}
      <div className={`agent-floating-widget ${isMinimized ? 'minimized' : ''}`}>
        {/* Widget Top Bar */}
        <div className="widget-topbar">
          <div className="widget-header-info">
            <div className={`widget-pulse-badge ${isFinished ? 'done' : error ? 'error' : 'live'}`}>
              <span className="pulse-dot" />
              {isFinished ? 'Execution Complete' : error ? 'Execution Failed' : 'Multi-Agent Pipeline Live'}
            </div>
            <h3 className="widget-title">
              {isFinished
                ? 'All Agents Completed Workflow'
                : activeAgentName || currentStepInfo.agent}
            </h3>
          </div>

          <div className="widget-controls">
            <span className="widget-timer">{elapsed}s</span>
            <button
              className="widget-icon-btn"
              onClick={() => setIsMinimized(!isMinimized)}
              title={isMinimized ? 'Expand Widget' : 'Minimize Widget'}
            >
              {isMinimized ? '▲' : '▼'}
            </button>
            <button className="widget-icon-btn close" onClick={onComplete} title="Close Widget">
              ✕
            </button>
          </div>
        </div>

        {/* Progress Rail */}
        <div className="widget-progress-rail">
          <div className="widget-progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>

        {!isMinimized && (
          <div className="widget-content-body">
            {/* Step Pipeline Pills */}
            <div className="widget-step-pills">
              {pipelineSteps.map((step, idx) => {
                const isDone = isFinished || idx < currentStepIndex
                const isCurrent = !isFinished && idx === currentStepIndex
                return (
                  <div
                    key={step.name}
                    className={`step-pill ${isDone ? 'done' : isCurrent ? 'current' : 'pending'}`}
                    title={step.agent}
                  >
                    <span className="step-pill-icon">{step.icon}</span>
                    <span className="step-pill-name">{step.name}</span>
                    {isDone && <span className="step-pill-check">✓</span>}
                    {isCurrent && <span className="step-pill-spinner" />}
                  </div>
                )
              })}
            </div>



            {/* Live Terminal Log Console Stream */}
            <div className="widget-short-logs">
              <div className="short-logs-bar">
                <span className="terminal-title-text">Live Agent Log Console ({logs.length})</span>
                <button
                  className="toggle-logs-btn"
                  onClick={() => setIsExpandedLogs(!isExpandedLogs)}
                >
                  {isExpandedLogs ? 'Hide Console' : 'Show Console'}
                </button>
              </div>

              {isExpandedLogs && (
                <div className="short-logs-console">
                  {logs.map((log, i) => (
                    <div key={i} className={`console-line ${log.type || 'info'}`}>
                      <span className="c-time">[{log.time}]</span>
                      <span className="c-agent">{log.agent}:</span>
                      <span className="c-msg">{log.message}</span>
                    </div>
                  ))}
                  <div ref={logsEndRef} />
                </div>
              )}
            </div>

            {/* Completion Action Button */}
            {isFinished && (
              <button className="accent-button full-width widget-finish-btn" onClick={onComplete}>
                Explore Career Path & Training Plan <span>↓</span>
              </button>
            )}
          </div>
        )}
      </div>
    </>
  )
}
