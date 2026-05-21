// ClarityOS desktop — renderer entry. Mounts the React tree under
// the #root div in index.html. The Electron main process loads either
// the dev server (development) or the built dist/index.html
// (production), and either way this file is the entrypoint.

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
// v1 surface tokens + minimal globals load BEFORE styles.css so legacy
// rules (auth shell, etc.) can override the v1 reset where they need to.
import "./tokens.css";
import "./styles/v1-globals.css";
import "./styles.css";

const root = document.getElementById("root");
if (!root) {
  throw new Error("ClarityOS: #root not found in index.html");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
