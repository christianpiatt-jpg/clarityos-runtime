import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import App from "./App";
// v1 surface tokens — coexist with the legacy --os-* tokens that
// styles/app.css already provides. v1 components only reference the
// --color-* / --space-* / --font-* / --radius-* vars defined here.
import "./v1-tokens.css";
import "./styles/v1-globals.css";
import "./styles/app.css";

// Mount selection:
//   • #root            — standalone deploy (default index.html)
//   • #clarityos-root  — embed mode (WordPress plugin / host-page mount)
// When mounted in embed mode we use HashRouter so the host URL stays put
// (e.g. https://pro-mediations.com/clarityos/#/threads) — the host
// page's slug doesn't have to match any ClarityOS route.
const standaloneRoot = document.getElementById("root");
const embedRoot = document.getElementById("clarityos-root");
const rootEl = standaloneRoot ?? embedRoot;
if (!rootEl) {
  throw new Error("ClarityOS mount missing: expected #root or #clarityos-root");
}
const isEmbed = !standaloneRoot && !!embedRoot;
const Router = isEmbed ? HashRouter : BrowserRouter;

createRoot(rootEl).render(
  <React.StrictMode>
    <Router>
      <App />
    </Router>
  </React.StrictMode>
);
