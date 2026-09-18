import './dashboard.css'

document.querySelector('#app').innerHTML = `
  <div class="dashboard-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div>
          <h2>SkillBridge</h2>
        </div>
      </div>

      <nav class="nav">
        <a class="active" href="#">Dashboard</a>
        <a href="/profile-parsing/">Profile Parsing</a>
        <a href="#">Skill Gap Analysis</a>
        <a href="#">Skill Matching</a>
        <a href="#">Training Agent</a>
      </nav>
    </aside>

    <main class="main-panel">
      <header class="topbar">
        <div>
          <p class="eyebrow">Hackathon project</p>
          <h1>Career Intelligence Dashboard</h1>
        </div>
        <a class="primary-btn" href="/profile-parsing/">Run Analysis</a>
      </header>

      <section class="stats-grid">
        <article class="stat-card accent">
          <span class="label">Profiles Parsed</span>
          <strong>128</strong>
          <small>+12% this week</small>
        </article>
        <article class="stat-card">
          <span class="label">Skills Matched</span>
          <strong>84%</strong>
          <small>Average fit score</small>
        </article>
        <article class="stat-card">
          <span class="label">Training Paths</span>
          <strong>27</strong>
          <small>Recommended</small>
        </article>
      </section>

      <section class="content-grid">
        <article class="panel">
          <div class="panel-header">
            <h3>Active Agent Workflow</h3>
            <span class="status-pill">Live</span>
          </div>
          <ul class="timeline">
            <li><span class="dot success"></span> Resume parsing completed</li>
            <li><span class="dot success"></span> Skill gap analysis generated</li>
            <li><span class="dot pending"></span> Job matching review in progress</li>
            <li><span class="dot pending"></span> Training recommendations pending</li>
          </ul>
        </article>

        <article class="panel">
          <div class="panel-header">
            <h3>Latest Profile</h3>
            <span class="meta">AI parsed</span>
          </div>
          <div class="profile-box">
            <h4>Aisha Rahman</h4>
            <p>Full Stack Developer</p>
            <ul>
              <li>React</li>
              <li>Python</li>
              <li>MongoDB</li>
            </ul>
          </div>
        </article>
      </section>
    </main>
  </div>
`
