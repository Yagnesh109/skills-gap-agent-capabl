const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Service to communicate with Backend Gap Analysis Agent endpoints.
 */
export const gapAnalysisService = {
  /**
   * Request skill gap analysis report for given candidate skills and target role.
   * @param {Object} payload
   * @param {string[]} payload.candidate_skills
   * @param {string} payload.target_role
   * @param {string} [payload.target_job_description]
   * @param {string[]} [payload.required_skills]
   */
  async analyzeGaps(payload) {
    const response = await fetch(`${API_BASE_URL}/api/gap-analysis/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Gap analysis failed with status: ${response.status}`);
    }

    return await response.json();
  },

  /**
   * Health check for Gap Analysis Agent.
   */
  async checkHealth() {
    const response = await fetch(`${API_BASE_URL}/api/gap-analysis/health`);
    return await response.json();
  },
};
