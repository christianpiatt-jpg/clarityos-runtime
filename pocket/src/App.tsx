import { Routes, Route, Link } from "react-router-dom";

import HomeRoute from "./routes/index";
import RuntimeRoute from "./routes/runtime";

export default function App() {
  return (
    <div className="pocket-root">
      <nav className="pocket-nav">
        <Link to="/">Home</Link>
        <Link to="/runtime">Runtime</Link>
      </nav>
      <main className="pocket-main">
        <Routes>
          <Route path="/" element={<HomeRoute />} />
          <Route path="/runtime" element={<RuntimeRoute />} />
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
