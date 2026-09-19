import React, { useState } from "react";
import { skillMatchService } from "./skillMatchService";

/**
 * SkillMatchView Component Skeleton.
 * Provides UI interface for inputting candidate skills and reviewing matched job results.
 */
export const SkillMatchView = () => {
  const [jobTitle, setJobTitle] = useState("");
  const [skillsInput, setSkillsInput] = useState("");
  const [matches, setMatches] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleMatch = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const candidateSkills = skillsInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);

      const result = await skillMatchService.matchSkills({
        candidate_skills: candidateSkills,
        job_title: jobTitle,
      });

      setMatches(result.matches || []);
    } catch (err) {
      setError(err.message || "Failed to match skills");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="skill-match-container">
      <h2>Skill Matching Agent</h2>
      <form onSubmit={handleMatch} className="skill-match-form">
        <div className="form-group">
          <label htmlFor="jobTitle">Target Job Title</label>
          <input
            id="jobTitle"
            type="text"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            placeholder="e.g. Backend Developer"
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="skillsInput">Candidate Skills (comma-separated)</label>
          <input
            id="skillsInput"
            type="text"
            value={skillsInput}
            onChange={(e) => setSkillsInput(e.target.value)}
            placeholder="e.g. Python, FastAPI, Docker, SQL"
            required
          />
        </div>

        <button type="submit" disabled={isLoading}>
          {isLoading ? "Matching..." : "Find Matching Jobs"}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}

      <div className="results-container">
        <h3>Matched Results ({matches.length})</h3>
        {matches.length === 0 && !isLoading && (
          <p>No job matches found yet. Submit candidate skills above.</p>
        )}
      </div>
    </div>
  );
};

export default SkillMatchView;
