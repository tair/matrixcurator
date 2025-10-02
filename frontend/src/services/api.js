import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8001";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

export const apiService = {
  // Custom LLM operations
  async testExtraction(context, prompt) {
    const response = await api.post("/api/custom-extraction", {
      context,
      prompt,
    });
    return response.data;
  },

  async testEvaluation(context, extractionResult) {
    const response = await api.post("/api/custom-evaluation", {
      context,
      extraction_result: extractionResult,
    });
    return response.data;
  },
};

export default api;
