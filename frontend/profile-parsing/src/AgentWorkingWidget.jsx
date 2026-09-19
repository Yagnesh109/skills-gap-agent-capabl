import React, { useEffect, useRef, useState } from 'react'

const pipelineSteps = [
  { node: 'profile_parsing', name: 'Profile Parse', icon: '🧾' },
  { node: 'job_search', name: 'Job Search', icon: '🔍' },
  { node: 'rag_retrieval', name: 'RAG Retrieval', icon: '📚' },
  { node: 'skill_matching', name: 'Skill Matching', icon: '🧠' },
  { node: 'gap_analysis', name: 'Gap Analysis', icon: '⚡' },
  { node: 'opportunity_simulation', name: 'Opportunity Sim', icon: '📈' },
  { node: 'time_to_ready', name: 'Time-to-Ready', icon: '⏱️' },
  { node: 'gemini_reasoning', name: 'AI Reasoning', icon: '🤖' },
  { node: 'training_recommendations', name: 'Training', icon: '🎓' },
  { node: 'report', name: 'Report', icon: '📝' },
]

function eventTime(timestamp) {
  if (!timestamp) return '--:--:--'
  return new Date(timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })
}

export function AgentWorkingWidget({ isOpen, events = [], runStatus, error, disconnected, onComplete }) {
  const [isMinimized, setIsMinimized] = useState(false)
  const [isExpandedLogs, setIsExpandedLogs] = useState(true)
  const logsEndRef = useRef(null)

  useEffect(() => {
    if (logsEndRef.current && isExpandedLogs) logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [events, isExpandedLogs])

  if (!isOpen) return null

  const latestByNode = events.reduce((acc, event) => ({ ...acc, [event.node]: event }), {})
  const completedCount = pipelineSteps.filter(({ node }) => latestByNode[node]?.status === 'completed').length
  const latestEvent = events[events.length - 1]
  const isFinished = runStatus === 'completed'
  const isFailed = runStatus === 'failed'
  const title = isFinished ? 'All agents completed workflow' : isFailed ? 'Workflow needs attention' : latestEvent?.label || 'Waiting for agent events'

  return (
    <>
      <div className={`agent-backdrop-fade ${isFinished || isFailed ? 'fading-out' : ''}`} />
      <div className={`agent-floating-widget ${isMinimized ? 'minimized' : ''}`}>
        <div className="widget-topbar">
          <div className="widget-header-info">
            <div className={`widget-pulse-badge ${isFinished ? 'done' : isFailed ? 'error' : 'live'}`}>
              <span className="pulse-dot" />
              {isFinished ? 'Execution Complete' : isFailed ? 'Execution Failed' : 'Live Agent Progress'}
            </div>
            <h3 className="widget-title">{title}</h3>
          </div>
          <div className="widget-controls">
            <span className="widget-timer">{completedCount}/{pipelineSteps.length} stages</span>
            <button className="widget-icon-btn" onClick={() => setIsMinimized(!isMinimized)} title={isMinimized ? 'Expand Widget' : 'Minimize Widget'}>{isMinimized ? '▲' : '▼'}</button>
            <button className="widget-icon-btn close" onClick={onComplete} title="Close Widget">✕</button>
          </div>
        </div>

        {!isMinimized && (
          <div className="widget-content-body">
            <div className="widget-progress-rail" aria-label={`${completedCount} of ${pipelineSteps.length} stages completed`}>
              <div className="widget-progress-fill" style={{ width: `${Math.round((completedCount / pipelineSteps.length) * 100)}%` }} />
            </div>
            <div className="widget-step-pills">
              {pipelineSteps.map((step) => {
                const current = latestByNode[step.node]
                const stepStatus = current?.status || 'pending'
                return (
                  <div key={step.node} className={`step-pill ${stepStatus === 'completed' ? 'done' : stepStatus === 'running' ? 'current' : stepStatus === 'failed' ? 'failed' : 'pending'}`} title={current?.message || step.name}>
                    <span className="step-pill-icon">{step.icon}</span>
                    <span className="step-pill-name">{step.name}</span>
                    {stepStatus === 'completed' && <span className="step-pill-check">✓</span>}
                    {stepStatus === 'running' && <span className="step-pill-spinner" />}
                    {stepStatus === 'failed' && <span className="step-pill-check">✕</span>}
                  </div>
                )
              })}
            </div>
            {disconnected && <div className="widget-inline-warning">Live connection interrupted; the browser is retrying.</div>}
            {error && <div className="widget-inline-error">{error}</div>}
            <div className="widget-short-logs">
              <div className="short-logs-bar">
                <span className="terminal-title-text">Live Agent Log Console ({events.length})</span>
                <button className="toggle-logs-btn" onClick={() => setIsExpandedLogs(!isExpandedLogs)}>{isExpandedLogs ? 'Hide Console' : 'Show Console'}</button>
              </div>
              {isExpandedLogs && <div className="short-logs-console">
                {events.map((event, index) => <div key={`${event.timestamp}-${event.node}-${index}`} className={`console-line ${event.status === 'failed' ? 'error' : event.status === 'completed' ? 'success' : 'info'}`}>
                  <span className="c-time">[{eventTime(event.timestamp)}]</span>
                  <span className="c-agent">{event.label || event.node}:</span>
                  <span className="c-msg">{event.message}</span>
                </div>)}
                <div ref={logsEndRef} />
              </div>}
            </div>
            {isFinished && <button className="accent-button full-width widget-finish-btn" onClick={onComplete}>Explore Career Path & Training Plan <span>↓</span></button>}
          </div>
        )}
      </div>
    </>
  )
}
