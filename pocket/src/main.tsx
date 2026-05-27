import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { hydrateSessionOnLoad } from "./api/client";
import "./styles/app.css";

// v0.3.4: drop any expired session BEFORE React mounts so the
// first paint reflects the correct authed/unauthed state. Cheap;
// idempotent.
hydrateSessionOnLoad();

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Pocket: #root element missing from index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
