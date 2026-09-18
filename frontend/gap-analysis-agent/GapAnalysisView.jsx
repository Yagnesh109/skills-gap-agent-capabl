import React, { useState } from "react";
import { gapAnalysisService } from "./gapAnalysisService";

/**
 * GapAnalysisView Component Skeleton.
 * Provides UI interface for inputting candidate skills, role goals, and reviewing gap analysis reports.
 */
export const GapAnalysisView = () => {
  const [targetRole, setTargetRole] = useState("");
  const [candidateSkills, setCandidateSkills] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [report, setReport] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const skills = candidateSkills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const result = await gapAnalysisService.analyzeGaps({
        candidate_skills: skills,
        target_role: targetRole,
        target_job_description: jobDescription,
      });

      setReport(result);
    } catch (err) {
      setError(err.message || "Failed to run gap analysis");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="gap-analysis-container">
      <h2>Gap Analysis Agent</h2>
      <form onSubmit={handleAnalyze} className="gap-analysis-form">
        <div className="form-group">
          <label htmlFor="targetRole">Target Career Role</label>
          <input
            id="targetRole"
            type="text"
            value={targetRole}
            onChange={(e) => setTargetRole(e.target.value)}
            placeholder="e.g. Senior Machine Learning Engineer"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="candidateSkills">Candidate Skills (comma-separated)</label>
          <input
            id="candidateSkills"
            type="text"
            value={candidateSkills}
            onChange={(e) => setCandidateSkills(e.target.value)}
            placeholder="e.g. Python, Scikit-learn, SQL"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="jobDescription">Target Job Description (Optional)</label>
          <textarea
            id="jobDescription"
            rows={4}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste relevant job description snippet..."
          />
        </div>

        <button type="submit" disabled={isLoading}>
          {isLoading ? "Analyzing Gaps..." : "Run Gap Analysis"}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}

      <div className="report-container">
        <h3>Analysis Report</h3>
        {!report && !isLoading && (
          <p>No gap analysis generated yet. Submit candidate skills and target role above.</p>
        )}
        {report && (
          <div className="report-content">
            <p><strong>Target Role:</strong> {report.target_role}</p>
            <p><strong>Readiness Score:</strong> {report.readiness_score}%</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default GapAnalysisView;
