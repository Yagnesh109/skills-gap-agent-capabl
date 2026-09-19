import { jsPDF } from 'jspdf'

/**
 * Report Generation Agent
 * Compiles a formal, highly descriptive executive PDF report featuring
 * career profile metrics, market job matches, skill gap analysis, and course links.
 */
export function generatePdfReport({ profile, workflow, targetRole, location }) {
  const doc = new jsPDF({ unit: 'pt', format: 'a4' })
  const pageWidth = doc.internal.pageSize.getWidth()
  const pageHeight = doc.internal.pageSize.getHeight()

  const matchedJobs = workflow?.matched_jobs || workflow?.matching_results || []
  const gaps = workflow?.skill_gaps || workflow?.gap_analyses || []
  const opportunities = workflow?.opportunity_analysis?.opportunities || []
  const courses = workflow?.training_recommendations || []
  const missingSkills = [...new Set(gaps.flatMap((gap) => gap.missing_skills || []))]
  const currentJobs = workflow?.current_jobs ?? workflow?.opportunity_analysis?.current_jobs ?? 0

  let y = 45

  // Primary Colors (Formal Slate & Indigo Palette)
  const primaryColor = [15, 23, 42]   // #0f172a
  const indigoColor = [79, 70, 229]   // #4f46e5
  const emeraldColor = [16, 185, 129] // #10b981
  const slateMuted = [100, 116, 139]  // #64748b
  const bgLight = [248, 250, 252]     // #f8fafc

  // Header Banner
  doc.setFillColor(...primaryColor)
  doc.rect(0, 0, pageWidth, 90, 'F')

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(22)
  doc.setTextColor(255, 255, 255)
  doc.text('PATHWISE', 40, 48)

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(11)
  doc.setTextColor(165, 180, 252)
  doc.text('Executive Career Intelligence & Skill Gap Analysis Report', 40, 68)

  doc.setFontSize(9)
  doc.setTextColor(203, 213, 225)
  const dateStr = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  doc.text(`Generated: ${dateStr}`, pageWidth - 160, 48)
  doc.text('Confidential Career Assessment', pageWidth - 180, 68)

  y = 115

  // 1. Executive Summary & Profile Intent
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...primaryColor)
  doc.text('1. EXECUTIVE SUMMARY & PROFILE SNAPSHOT', 40, y)
  y += 14

  doc.setDrawColor(226, 232, 240)
  doc.setFillColor(...bgLight)
  doc.roundedRect(40, y, pageWidth - 80, 80, 8, 8, 'FD')

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(11)
  doc.setTextColor(...primaryColor)
  doc.text(`Candidate Name: ${profile?.name || 'Candidate Profile'}`, 55, y + 24)

  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10)
  doc.setTextColor(...slateMuted)
  doc.text(`Target Role Goal: ${targetRole || profile?.target_role || 'Software Engineer'}`, 55, y + 42)
  doc.text(`Preferred Location: ${location || profile?.location || 'Flexible / Remote'}`, 300, y + 42)

  const detectedSkills = (profile?.skills || []).slice(0, 8).join(', ') || 'Extracted skills loaded'
  doc.text(`Core Verified Skills: ${detectedSkills}`, 55, y + 60)

  y += 105

  // 2. Market Metrics Overview
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...primaryColor)
  doc.text('2. MARKET FIT & READINESS METRICS', 40, y)
  y += 14

  const metricWidth = (pageWidth - 80 - 30) / 4
  const metricsData = [
    { label: 'Current Fit Jobs', val: `${currentJobs}` },
    { label: 'Market Jobs Evaluated', val: `${matchedJobs.length}` },
    { label: 'Key Skill Gaps', val: `${missingSkills.length}` },
    { label: 'Suggested Courses', val: `${courses.length}` },
  ]

  metricsData.forEach((m, idx) => {
    const mx = 40 + idx * (metricWidth + 10)
    doc.setFillColor(...bgLight)
    doc.roundedRect(mx, y, metricWidth, 52, 6, 6, 'FD')

    doc.setFont('helvetica', 'bold')
    doc.setFontSize(15)
    doc.setTextColor(...indigoColor)
    doc.text(m.val, mx + 16, y + 24)

    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    doc.setTextColor(...slateMuted)
    doc.text(m.label, mx + 16, y + 40)
  })

  y += 75

  // 3. Top Market Job Matches
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...primaryColor)
  doc.text('3. TOP MATCHED CAREER OPPORTUNITIES', 40, y)
  y += 14

  if (matchedJobs.length > 0) {
    matchedJobs.slice(0, 4).forEach((job) => {
      doc.setFillColor(255, 255, 255)
      doc.roundedRect(40, y, pageWidth - 80, 46, 6, 6, 'FD')

      const matchScore = Math.round(job.match_score || 0)
      doc.setFillColor(238, 242, 255)
      doc.roundedRect(52, y + 9, 42, 28, 4, 4, 'F')
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(11)
      doc.setTextColor(...indigoColor)
      doc.text(`${matchScore}%`, 61, y + 26)

      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      doc.setTextColor(...primaryColor)
      doc.text(job.title || job.job_title || 'Untitled Role', 108, y + 21)

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(9)
      doc.setTextColor(...slateMuted)
      doc.text(`${job.company || 'Company undisclosed'} • ${job.location || 'Location flexible'}`, 108, y + 35)

      y += 52
    })
  } else {
    doc.setFont('helvetica', 'italic')
    doc.setFontSize(10)
    doc.setTextColor(...slateMuted)
    doc.text('No matching market job roles detected in this assessment run.', 50, y + 15)
    y += 30
  }

  y += 15

  // 4. Skill Gap Matrix & Job Unlock Multipliers
  if (y > pageHeight - 190) {
    doc.addPage()
    y = 50
  }

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...primaryColor)
  doc.text('4. SKILL GAP MATRIX & JOB UNLOCK MULTIPLIERS', 40, y)
  y += 14

  if (opportunities.length > 0) {
    opportunities.slice(0, 4).forEach((item) => {
      doc.setFillColor(...bgLight)
      doc.roundedRect(40, y, pageWidth - 80, 36, 6, 6, 'FD')

      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      doc.setTextColor(...primaryColor)
      doc.text(item.skill, 55, y + 22)

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(9)
      doc.setTextColor(...slateMuted)
      doc.text(item.duration_weeks ? `${item.duration_weeks} weeks estimated learning` : 'High priority market demand signal', 210, y + 22)

      doc.setFont('helvetica', 'bold')
      doc.setFontSize(11)
      doc.setTextColor(...indigoColor)
      doc.text(`+${item.jobs_unlocked} jobs unlocked`, pageWidth - 165, y + 22)

      y += 42
    })
  } else if (missingSkills.length > 0) {
    missingSkills.slice(0, 4).forEach((skill) => {
      doc.setFillColor(...bgLight)
      doc.roundedRect(40, y, pageWidth - 80, 32, 6, 6, 'FD')
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      doc.setTextColor(...primaryColor)
      doc.text(skill, 55, y + 20)
      y += 38
    })
  } else {
    doc.setFont('helvetica', 'italic')
    doc.setFontSize(10)
    doc.setTextColor(...slateMuted)
    doc.text('Your profile skills fully cover the target market role requirements.', 50, y + 15)
    y += 30
  }

  y += 15

  // 5. Recommended Training Pathways & Direct Course Links
  if (y > pageHeight - 200) {
    doc.addPage()
    y = 50
  }

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.setTextColor(...primaryColor)
  doc.text('5. RECOMMENDED TRAINING PATHWAYS & COURSE LINKS', 40, y)
  y += 14

  if (courses.length > 0) {
    courses.slice(0, 4).forEach((course) => {
      const cardHeight = course.url ? 68 : 52
      if (y + cardHeight > pageHeight - 40) {
        doc.addPage()
        y = 50
      }

      doc.setFillColor(255, 255, 255)
      doc.roundedRect(40, y, pageWidth - 80, cardHeight, 6, 6, 'FD')

      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      doc.setTextColor(...primaryColor)
      doc.text(course.course_name, 55, y + 20)

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(9)
      doc.setTextColor(...slateMuted)
      doc.text(`${course.provider || 'Coursera / Udemy'} • ${course.duration_weeks || '4'} weeks est.`, 55, y + 36)

      doc.setFont('helvetica', 'bold')
      doc.setFontSize(10)
      doc.setTextColor(...emeraldColor)
      doc.text(`+${course.jobs_unlocked || 1} jobs unlocked`, pageWidth - 165, y + 24)

      if (course.url) {
        doc.setFont('helvetica', 'normal')
        doc.setFontSize(9)
        doc.setTextColor(...indigoColor)
        const linkText = `Course Link: ${course.url}`
        doc.textWithLink(linkText, 55, y + 54, { url: course.url })
      }

      y += cardHeight + 8
    })
  } else {
    doc.setFont('helvetica', 'italic')
    doc.setFontSize(10)
    doc.setTextColor(...slateMuted)
    doc.text('No specialized course recommendations required for current skill coverage.', 50, y + 15)
    y += 30
  }

  // Formal Page Footer
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.setTextColor(...slateMuted)
  doc.text('Pathwise Multi-Agent Platform • Executive Report • Powered by LangGraph & Gemini 3.6', 40, pageHeight - 25)

  // Save PDF Document
  const candidateName = profile?.name || 'Candidate'
  const sanitizedName = candidateName.replace(/\s+/g, '_')
  const filename = `Pathwise_Career_Report_${sanitizedName}.pdf`
  doc.save(filename)
}
