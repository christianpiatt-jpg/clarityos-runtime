import { NavLink, Routes, Route, Link } from "react-router-dom";

import HomeRoute from "./routes/index";
import RuntimeRoute from "./routes/runtime";
import LoginRoute from "./routes/login";
import ClarifyRoute from "./routes/clarify";
import MeRoute from "./routes/me";
import RunsRoute from "./routes/runs";

const NAV_LINKS: { to: string; label: string }[] = [
  { to: "/",         label: "Home" },
  { to: "/runtime",  label: "Runtime" },
  { to: "/clarify",  label: "Clarify" },
  { to: "/me",       label: "Me" },
  { to: "/runs",     label: "Runs" },
  { to: "/login",    label: "Sign in" },
];

export default function App() {
  return (
    <div className="pocket-root">
      <nav className="pocket-nav">
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
      </nav>
      <main className="pocket-main">
        <Routes>
          <Route path="/"        element={<HomeRoute />} />
          <Route path="/runtime" element={<RuntimeRoute />} />
          <Route path="/login"   element={<LoginRoute />} />
          <Route path="/clarify" element={<ClarifyRoute />} />
          <Route path="/me"      element={<MeRoute />} />
          <Route path="/runs"    element={<RunsRoute />} />
          <Route
            path="*"
            element={
              <section className="pocket-notfound">
                <h1>Not found</h1>
                <p>
                  This Pocket route is not implemented yet. Back to{" "}
                  <Link to="/">Home</Link>.
                </p>
              </section>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
