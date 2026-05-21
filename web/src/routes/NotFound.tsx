import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div>
      <div className="panel">
        <h1>404</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          That route doesn't exist on this surface.
        </p>
        <div className="row" style={{ marginTop: 16 }}>
          <Link to="/" className="btn">HOME</Link>
          <Link to="/system" className="btn btn-secondary">SYSTEM</Link>
        </div>
      </div>
    </div>
  );
}
