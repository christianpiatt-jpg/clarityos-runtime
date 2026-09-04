import { Link } from "react-router-dom";
import { useIsController } from "../components/RequireAdmin";

export default function NotFound() {
  // #145 -- /system is the admin's; a member gets no door to it here.
  const admin = useIsController();
  return (
    <div>
      <div className="panel">
        <h1>404</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          That route doesn't exist on this surface.
        </p>
        <div className="row" style={{ marginTop: 16 }}>
          <Link to="/" className="btn">HOME</Link>
          {admin ? <Link to="/system" className="btn btn-secondary">SYSTEM</Link> : null}
        </div>
      </div>
    </div>
  );
}
