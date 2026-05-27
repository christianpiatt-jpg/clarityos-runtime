import { NavLink, Routes, Route, Link } from "react-router-dom";

import HomeRoute from "./routes/index";
import RuntimeRoute from "./routes/runtime";
import LoginRoute from "./routes/login";
import ClarifyRoute from "./routes/clarify";
import MeRoute from "./routes/me";
import RunsRoute from "./routes/runs";
import LandingRoute from "./routes/landing";
import PrivacyRoute from "./routes/privacy";
import TermsRoute from "./routes/terms";
import OperatorStateRoute from "./routes/operator-state";
import MeStatus from "./components/MeStatus";
import ThemeToggle from "./components/ThemeToggle";

const NAV_LINKS: { to: string; label: string }[] = [
  { to: "/",               label: "Home" },
  { to: "/runtime",        label: "Runtime" },
  { to: "/clarify",        label: "Clarify" },
  { to: "/me",             label: "Me" },
  { to: "/runs",           label: "Runs" },
  { to: "/operator/state", label: "Operator" },
  { to: "/login",          label: "Sign in" },
  { to: "/landing",        label: "Landing" },
];

export default function App() {
  return (
    <div className="pocket-root">
      <nav className="pocket-nav" aria-label="Primary">
        <div className="pocket-nav-links">
          {NAV_LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                isActive ? "pocket-navlink active" : "pocket-navlink"
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
        <MeStatus />
        <ThemeToggle />
      </nav>
      <main className="pocket-main">
        <Routes>
          <Route path="/"               element={<HomeRoute />} />
          <Route path="/runtime"        element={<RuntimeRoute />} />
          <Route path="/login"          element={<LoginRoute />} />
          <Route path="/clarify"        element={<ClarifyRoute />} />
          <Route path="/me"             element={<MeRoute />} />
          <Route path="/runs"           element={<RunsRoute />} />
          <Route path="/landing"        element={<LandingRoute />} />
          <Route path="/privacy"        element={<PrivacyRoute />} />
          <Route path="/terms"          element={<TermsRoute />} />
          <Route path="/operator/state" element={<OperatorStateRoute />} />
          <Route
            path="*"
            element={
              <div className="pkt-card is-padded">
                <h1>Not found</h1>
                <p className="pocket-muted">
                  This Pocket route is not implemented yet. Back to{" "}
                  <Link to="/">Home</Link>.
                </p>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
