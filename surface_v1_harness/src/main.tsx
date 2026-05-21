import React from "react";
import ReactDOM from "react-dom/client";

// tokens.css MUST load before any module-css that reads var(--…).
// Vite hoists CSS imports per module, but explicit ordering at the
// entry point is the safest guarantee.
import "./tokens/tokens.css";
import "./styles/global.css";

import App from "./App";

const root = document.getElementById("root");
if (!root) throw new Error("missing #root element");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
