import "./App.css";
import CustomExtraction from "./components/CustomExtraction";

function App() {
  return (
    <div className="app">
      <div className="header">
        <h1>🧬 MatrixCurator</h1>
        <p>LLM-Powered Phylogenetic Character Extraction Demo</p>
      </div>

      <div className="container">
        <CustomExtraction />
      </div>
    </div>
  );
}

export default App;
