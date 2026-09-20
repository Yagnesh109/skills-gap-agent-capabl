import React, { useEffect, useRef, useState } from 'react'

const pipelineSteps = [
  { nodes: ['profile_parsing'], name: 'Profile Parse', icon: '🧾' },
  { nodes: ['job_search'], name: 'Job Search', icon: '🔍' },
  { nodes: ['rag_retrieval'], name: 'RAG Retrieval', icon: '📚' },
  { nodes: ['skill_matching'], name: 'Skill Matching', icon: '🧠' },
  { nodes: ['gap_analysis'], name: 'Gap Analysis', icon: '⚡' },
  { nodes: ['time_to_ready', 'gemini_reasoning', 'deterministic_explanation'], name: 'Readiness + AI Reasoning', icon: '🤖' },
  { nodes: ['training_recommendations'], name: 'Training Path', icon: '🎓' },
]

function eventTime(timestamp) {
  if (!timestamp) return '--:--:--'
  return new Date(timestamp).toLocaleTimeString([], { hour12: false, second: '2-digit' })
}

export function AgentWorkingWidget({ isOpen, events = [], runStatus, error, disconnected, onComplete, onOpen, onChat }) {
  const [isMinimized, setIsMinimized] = useState(false)
  const [isExpandedLogs, setIsExpandedLogs] = useState(true)
  const logsEndRef = useRef(null)

  useEffect(() => {
    if (logsEndRef.current && isExpandedLogs) logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [events, isExpandedLogs])

  if (!isOpen) {
    return events.length > 0 ? (
      <button className="agent-log-launcher" onClick={onOpen} title="Open agent activity log" aria-label="Open agent activity log">
        <span className="agent-log-launcher-dot" />
        <span>⌁</span>
      </button>
    ) : null
  }

  const latestByNode = events.reduce((acc, event) => ({ ...acc, [event.node]: event }), {})
  const getStepStatus = (step) => {
    const stepEvents = step.nodes.map((node) => latestByNode[node]).filter(Boolean)
    if (step.nodes.includes('time_to_ready')) {
      if (stepEvents.some((event) => event.status === 'failed')) return 'failed'
      const readinessComplete = latestByNode.time_to_ready?.status === 'completed'
        && /analysis generated|analysis complete/i.test(latestByNode.time_to_ready?.message || '')
      if (readinessComplete || (runStatus === 'completed' && latestByNode.time_to_ready?.status === 'completed')) return 'completed'
      if (latestByNode.time_to_ready?.status === 'running' || latestByNode.time_to_ready?.status === 'completed') return 'running'
      return 'pending'
    }
    const latest = stepEvents[stepEvents.length - 1]
    if (latest?.status) return latest.status
    const stepIndex = pipelineSteps.indexOf(step)
    const previousStepsComplete = stepIndex > 0 && pipelineSteps
      .slice(0, stepIndex)
      .every((previousStep) => getStepStatus(previousStep) === 'completed')
    return previousStepsComplete ? 'running' : 'pending'
  }
  const completedCount = pipelineSteps.filter((step) => getStepStatus(step) === 'completed').length
  const latestEvent = events && events.length > 0 ? events[events.length - 1] : null
  const isWorkflowEventComplete = latestEvent?.node === 'workflow' && latestEvent?.status === 'completed'
  const isFinished = runStatus === 'completed' || isWorkflowEventComplete
  const isFailed = runStatus === 'failed' || (latestEvent?.node === 'workflow' && latestEvent?.status === 'failed')
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
                const current = step.nodes.map((node) => latestByNode[node]).filter(Boolean).pop()
                const stepStatus = getStepStatus(step)
                return (
                  <div key={step.name} className={`step-pill ${stepStatus === 'completed' ? 'done' : stepStatus === 'running' ? 'current' : stepStatus === 'failed' ? 'failed' : 'pending'}`} title={current?.message || step.name}>
                    <span className="step-pill-icon"><img src="/agenticon.png" alt="" /></span>
                    <span className="step-pill-name">{step.name}</span>
                    {stepStatus === 'completed' && <span className="step-pill-check">✓</span>}
                    {stepStatus === 'running' && <span className="step-pill-spinner" />}
                    {stepStatus === 'failed' && <span className="step-pill-check">✕</span>}
                  </div>
                )
              })}
            </div>
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
            {isFinished && (
              <div className="widget-finished-actions">
                <button className="accent-button full-width widget-finish-btn" onClick={onComplete}>View Analysis Results <span>↓</span></button>
                <button className="ghost-button full-width widget-chat-btn" onClick={onChat}>Talk to Resume Agent <span>✦</span></button>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
