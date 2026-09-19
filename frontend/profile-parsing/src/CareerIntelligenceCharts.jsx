import React from 'react'

function ChartShell({ title, description, children }) {
  return (
    <article className="career-chart-card">
      <div className="career-chart-heading">
        <h3>{title}</h3>
        <span>{description}</span>
      </div>
      {children}
    </article>
  )
}

export function SkillGapChart({ data = [] }) {
  const maximum = Math.max(...data.map((item) => Number(item.job_count || 0)), 1)
  return (
    <ChartShell title="Skill Gap" description="Missing skills across relevant jobs">
      {data.length ? (
        <div className="career-bar-list">
          {data.map((item) => (
            <div className="career-bar-row" key={item.skill}>
              <span>{item.skill}</span>
              <div className="career-bar-track"><div className="career-bar-fill gap" style={{ width: `${(Number(item.job_count || 0) / maximum) * 100}%` }} /></div>
              <b>{item.job_count} jobs</b>
            </div>
          ))}
        </div>
      ) : <div className="career-chart-empty">No meaningful skill gaps available yet.</div>}
    </ChartShell>
  )
}

export function OpportunityUnlockChart({ data = [] }) {
  const maximum = Math.max(...data.map((item) => Number(item.jobs_unlocked || 0)), 1)
  return (
    <ChartShell title="Opportunity Unlock" description="Additional jobs from one new skill">
      {data.length ? (
        <div className="career-bar-list">
          {data.map((item) => (
            <div className="career-bar-row" key={item.skill}>
              <span>{item.skill}</span>
              <div className="career-bar-track"><div className="career-bar-fill opportunity" style={{ width: `${(Number(item.jobs_unlocked || 0) / maximum) * 100}%` }} /></div>
              <b>+{item.jobs_unlocked}</b>
            </div>
          ))}
        </div>
      ) : <div className="career-chart-empty">No additional opportunities identified yet.</div>}
    </ChartShell>
  )
}

export function SkillCoverageChart({ data }) {
  if (!data) {
    return <ChartShell title="Your Profile" description="Current skill coverage"><div className="career-chart-empty">Skill coverage will appear after profile analysis.</div></ChartShell>
  }
  const matched = Number(data.matched_percentage || 0)
  const missing = Number(data.missing_percentage || 0)
  return (
    <ChartShell title="Your Profile" description="Current skill coverage">
      <div className="coverage-chart-content">
        <div className="coverage-donut" style={{ background: `conic-gradient(var(--emerald-500) 0 ${matched}%, var(--rose-200, #fecdd3) ${matched}% 100%)` }}>
          <div><strong>{matched}%</strong><span>Matched</span></div>
        </div>
        <div className="coverage-legend">
          <span><i className="legend-dot matched" />Matched <b>{matched}%</b></span>
          <span><i className="legend-dot missing" />Missing <b>{missing}%</b></span>
        </div>
      </div>
    </ChartShell>
  )
}
