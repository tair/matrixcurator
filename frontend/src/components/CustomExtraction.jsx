import { useState } from "react";
import { apiService } from "../services/api";

function CustomExtraction() {
  const [context, setContext] = useState(
    `The Archaeopteryx lithographica is a remarkable transitional fossil. 
This specimen exhibits several key characteristics:
- Feathers: present along wings and tail
- Wings: fully developed with flight feathers
- Teeth: present in jaw (reptilian feature)
- Tail: long bony tail with feathers
Geographic distribution includes Bavaria (Germany) and Wyoming (United States).`
  );
  const [prompt, setPrompt] = useState(
    "Extract the character 'Feathers' and list all possible states mentioned in the context."
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleExtract = async () => {
    if (!context.trim() || !prompt.trim()) {
      setError("Please provide both context and prompt");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await apiService.testExtraction(context, prompt);
      setResult(data);
    } catch (err) {
      setError(
        err.response?.data?.detail || err.message || "Failed to extract"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2>✨ Custom Extraction</h2>

      <div className="info-section">
        <h4>Interactive Character Extraction</h4>
        <p>
          Provide your own context and extraction prompt to test the LLM's
          ability to identify phylogenetic characters and their states.
        </p>
      </div>

      <div className="form-group">
        <label htmlFor="context">Context (Scientific Text):</label>
        <textarea
          id="context"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          placeholder="Enter the scientific text containing character information..."
          rows={6}
        />
      </div>

      <div className="form-group">
        <label htmlFor="prompt">Extraction Prompt:</label>
        <textarea
          id="prompt"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter your extraction prompt..."
          rows={3}
        />
      </div>

      <button className="btn" onClick={handleExtract} disabled={loading}>
        {loading ? (
          <>
            <span className="loading-spinner"></span> Extracting...
          </>
        ) : (
          "Extract Character"
        )}
      </button>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && (
        <div className="result">
          <h3>Extraction Result</h3>

          <div className="result-item">
            <p>
              <strong>Character:</strong> {result.character}
            </p>

            {result.states && (
              <>
                <p>
                  <strong>States:</strong>
                </p>
                <ul className="states-list">
                  {result.states.map((state, idx) => (
                    <li key={idx}>{state}</li>
                  ))}
                </ul>
              </>
            )}

            {result.timestamp && (
              <p
                style={{
                  marginTop: "10px",
                  fontSize: "0.85em",
                  color: "#999",
                }}
              >
                Extracted at: {new Date(result.timestamp).toLocaleString()}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default CustomExtraction;
