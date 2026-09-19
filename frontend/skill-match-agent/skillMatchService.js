const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Service to communicate with Backend Skill Matching Agent endpoints.
 */
export const skillMatchService = {
  /**
   * Request matching jobs for given candidate skills and target title.
   * @param {Object} payload
   * @param {string[]} payload.candidate_skills
   * @param {string} payload.job_title
   * @param {string} [payload.location]
   * @param {number} [payload.top_k]
   */
  async matchSkills(payload) {
    const response = await fetch(`${API_BASE_URL}/api/skill-match/match`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Skill match failed with status: ${response.status}`);
    }

    return await response.json();
  },

  /**
   * Health check for Skill Match Agent.
   */
  async checkHealth() {
    const response = await fetch(`${API_BASE_URL}/api/skill-match/health`);
    return await response.json();
  },
};
