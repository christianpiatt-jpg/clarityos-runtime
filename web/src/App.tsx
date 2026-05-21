import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import Home from "./routes/Home";
import Login from "./routes/Login";
import Operator from "./routes/Operator";
import Sessions from "./routes/Sessions";
import Continuity from "./routes/Continuity";
import Markov from "./routes/Markov";
import System from "./routes/System";
import Vault from "./routes/Vault";
import Library from "./routes/Library";
import Timeline from "./routes/Timeline";
import Plans from "./routes/Plans";
import Account from "./routes/Account";
import Cockpit from "./routes/Cockpit";   // v28 — surface composite
import Elins from "./routes/Elins";       // v28 — ELINS feed + #G runner
import MembershipPage from "./routes/MembershipPage"; // v30 — Founding cohort + #G credits
import FounderWaitlist from "./routes/FounderWaitlist"; // v32 — founder waitlist console
import Founder from "./routes/Founder";                 // v33 — founder console
import Dashboard from "./routes/Dashboard";             // v38 — ELINS dashboard
import OperatorProfile from "./routes/OperatorProfile"; // v39 — founder operator profile
import Threads from "./routes/Threads";                 // v48 — Threads UI
import PersonalElins from "./routes/PersonalElins";     // v54-followup — Personal ELINS view
import Iframe from "./routes/Iframe";                   // bridges — external iframe surface
import Session from "./routes/Session";                 // v61 — operator session runtime UI
import SessionHistory from "./routes/SessionHistory";   // v63 — session history viewer
import OperatorVault from "./routes/OperatorVault";     // v63 — vault inspector
import ModelPreferences from "./routes/ModelPreferences"; // v64 — per-operator model prefs
import ProviderHealth from "./routes/ProviderHealth";    // v65 — provider health dashboard
import ProviderDashboard from "./routes/ProviderDashboard"; // v68 — unified provider dashboard (health + models + config)
import OperatorElins from "./routes/OperatorElins";          // v69 — EL/INS dashboard
import OperatorElinsMacro from "./routes/OperatorElinsMacro"; // v69 — EL/INS macro view
import OperatorElinsDashboard from "./routes/OperatorElinsDashboard"; // v70 — EL/INS unified dashboard
import OperatorElinsExport from "./routes/OperatorElinsExport";       // v71 — EL/INS export (JSON + PDF)
import OperatorElinsAnomalies from "./routes/OperatorElinsAnomalies"; // v72 — EL/INS anomalies
import OperatorElinsRollup from "./routes/OperatorElinsRollup";       // v72 — EL/INS roll-up
import OperatorTimeline from "./routes/OperatorTimeline";              // v73 — operator timeline
import OrgTimeline from "./routes/OrgTimeline";                        // v73 — org timeline (founder-gated)
import Unit84Layout from "./routes/Unit84/Layout";                     // v74 / Unit 84 — Founding 500 Subscription Gate
import FounderAcceptance from "./routes/FounderAcceptance"; // ACCEPTANCE: harness dashboard
import FounderAcceptanceRuns from "./routes/FounderAcceptanceRuns";       // ACCEPTANCE Phase 3C: recent runs
import FounderAcceptanceStability from "./routes/FounderAcceptanceStability"; // ACCEPTANCE Phase 3C: stability metrics
import FounderAcceptanceCurve from "./routes/FounderAcceptanceCurve";         // ACCEPTANCE Phase 5C: stability curve
import FounderAnalyticsQuality from "./routes/FounderAnalyticsQuality";       // ANALYTICS Phase 6B: run-quality scoring
import FounderTelemetry from "./routes/FounderTelemetry";                     // TELEMETRY Phase 7C: trust + drift
import FounderIdentity from "./routes/FounderIdentity";                       // IDENTITY  Phase 8C: coherence layer
import FounderConsole from "./routes/FounderConsole";                         // CONSOLE   Phase 9B: founder overview
import FounderSurfaces from "./routes/FounderSurfaces";                       // SURFACES  Phase 10C: surfaces unification
import FounderOperator from "./routes/FounderOperator";                       // OPERATOR  Phase 11C: operator mode posture
import FounderLaunch from "./routes/FounderLaunch";                           // LAUNCH    Phase 12C: launch readiness
import FounderPisPiss from "./routes/FounderPisPiss";                         // IDENTITY  Phase 13C: PIS / PISS dual-surface taxonomy
import FounderCategory from "./routes/FounderCategory";                       // CATEGORY  Phase 14C: category definition + external language
import NotFound from "./routes/NotFound";
import CockpitV2 from "./routes/CockpitV2";   // consolidated operator cockpit (additive)

export default function App() {
  return (
    <Routes>
      {/* CockpitV2 — consolidated operator cockpit. Additive + self-gated
          (renders its own login panel); bypasses Layout + RequireAuth so
          it owns the viewport. */}
      <Route path="/cockpit-v2" element={<CockpitV2 />} />

      {/* Surface 4 — v1 surface owns the full viewport for /threads.   */}
      {/* Bypasses Layout so its cockpit chrome (topbar/rail/footer)    */}
      {/* doesn't nest inside the v1 surface's own chrome.              */}
      {/* v54-followup — /personal-elins follows the same pattern.       */}
      <Route element={<RequireAuth />}>
        <Route path="/threads" element={<Threads />} />
        <Route path="/personal-elins" element={<PersonalElins />} />
        {/* v74 / Unit 84 — Founding 500 Subscription Gate. Owns the
            full viewport (Somatic canvas + 1px red boundary), so
            bypasses the cockpit chrome like /threads above. Auth
            required (post WordPress -> Stripe Checkout -> /auth/consume). */}
        <Route path="/founding500/confirm" element={<Unit84Layout />} />
      </Route>

      <Route element={<Layout />}>
        {/* Public */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/plans" element={<Plans />} />
        <Route path="/system" element={<System />} />

        {/* Authenticated */}
        <Route element={<RequireAuth />}>
          <Route path="/operator" element={<Operator />} />
          <Route path="/markov" element={<Markov />} />
          <Route path="/account" element={<Account />} />
          {/* bridges — external iframe surface. Layout-wrapped so the
              cockpit chrome (rail + status bar) stays available for
              navigation away. */}
          <Route path="/iframe" element={<Iframe />} />
          {/* v61 / Unit 44 — Operator session runtime UI. Open
              endpoint server-side (no auth required), but lives
              behind RequireAuth here so the operator_id passed to
              start_session is the authed user. Anonymous visitors
              can still drive the runtime through the route below
              (RequireAuth wraps it but the route also works with
              auth.user || "op_anon"). */}
          <Route path="/session" element={<Session />} />
          {/* v63 / Unit 47 — Read-only session history viewer. */}
          <Route path="/session/history" element={<SessionHistory />} />
          {/* v63 / Unit 48 — Read-only vault inspector. /operator-vault
              not /vault because the v1 storage layer already owns /vault
              for the legacy GCS-backed file vault — different concept,
              different storage layer, can't collide. */}
          <Route path="/operator-vault" element={<OperatorVault />} />
          {/* v64 / Unit 67 — per-operator model preferences UI. */}
          <Route path="/model-preferences" element={<ModelPreferences />} />
          {/* v65 / Unit 69 — provider health dashboard. */}
          <Route path="/provider-health" element={<ProviderHealth />} />
          {/* v68 / Unit 73 — unified provider dashboard (health + models + config). */}
          <Route path="/operator/providers" element={<ProviderDashboard />} />
          {/* v69 / Unit 74 — EL/INS reasoning-stability operator dashboard. */}
          <Route path="/operator/el_ins" element={<OperatorElins />} />
          <Route path="/operator/el_ins/macro" element={<OperatorElinsMacro />} />
          {/* v70 / Unit 77 — unified EL/INS dashboard (distribution + TSI + trend). */}
          <Route path="/operator/el_ins/dashboard" element={<OperatorElinsDashboard />} />
          {/* v71 / Unit 78 — EL/INS export (JSON + PDF) for Founding Cohort. */}
          <Route path="/operator/el_ins/export" element={<OperatorElinsExport />} />
          {/* v72 / Unit 80 — EL/INS anomaly alerts (operator-side). */}
          <Route path="/operator/el_ins/anomalies" element={<OperatorElinsAnomalies />} />
          {/* v72 / Unit 81 — EL/INS organizational roll-up (24h/7d/30d). */}
          <Route path="/operator/el_ins/rollup" element={<OperatorElinsRollup />} />
          {/* v73 / Unit 82 — Operator timeline (event log). */}
          <Route path="/operator/timeline" element={<OperatorTimeline />} />
          {/* v73 / Unit 83 — Org-level timeline (founder-gated server-side). */}
          <Route path="/org/el_ins/timeline" element={<OrgTimeline />} />
          {/* v48 — Threads route moved out of Layout above (Surface 4). */}
        </Route>

        {/* Local-only (work without auth) */}
        <Route path="/sessions" element={<Sessions />} />
        <Route path="/continuity" element={<Continuity />} />

        {/* Storage Layer v1 — server-authoritative; require auth */}
        <Route element={<RequireAuth />}>
          <Route path="/vault" element={<Vault />} />
          <Route path="/library" element={<Library />} />
          <Route path="/timeline" element={<Timeline />} />
        </Route>

        {/* v28 — Surface + Distribution layer; require auth */}
        <Route element={<RequireAuth />}>
          <Route path="/cockpit" element={<Cockpit />} />
          <Route path="/elins" element={<Elins />} />
        </Route>

        {/* v38 — ELINS interactive dashboard; require auth.
            Server gates by v28_surfaces flag. */}
        <Route element={<RequireAuth />}>
          <Route path="/dashboard" element={<Dashboard />} />
        </Route>

        {/* v30 — Membership + #G credits; require auth */}
        <Route element={<RequireAuth />}>
          <Route path="/membership" element={<MembershipPage />} />
        </Route>

        {/* v32 — Founder waitlist deep-link; require auth + founder cohort
            (the API gates this server-side; the route surface is visible to
            any authed user but /founder/waitlist returns 403 if not founder). */}
        {/* v33 — Founder console at /founder composes waitlist + DMs +
            membership ops + ELINS + #cmt. */}
        <Route element={<RequireAuth />}>
          <Route path="/founder" element={<Founder />} />
          <Route path="/founder/waitlist" element={<FounderWaitlist />} />
          <Route path="/founder/operator/:user_id" element={<OperatorProfile />} />
          {/* ACCEPTANCE: harness dashboard (server gates by founder cohort) */}
          <Route path="/founder/acceptance" element={<FounderAcceptance />} />
          {/* ACCEPTANCE Phase 3C: additive sub-views */}
          <Route path="/founder/acceptance/runs" element={<FounderAcceptanceRuns />} />
          <Route path="/founder/acceptance/stability" element={<FounderAcceptanceStability />} />
          {/* ACCEPTANCE Phase 5C: longitudinal stability curve */}
          <Route path="/founder/acceptance/curve" element={<FounderAcceptanceCurve />} />
          {/* ANALYTICS Phase 6B: run-quality scoring view */}
          <Route path="/founder/analytics/quality" element={<FounderAnalyticsQuality />} />
          {/* TELEMETRY Phase 7C: trust signal + narrative drift view */}
          <Route path="/founder/telemetry" element={<FounderTelemetry />} />
          {/* IDENTITY Phase 8C: coherence layer */}
          <Route path="/founder/identity" element={<FounderIdentity />} />
          {/* CONSOLE Phase 9B: founder overview */}
          <Route path="/founder/console" element={<FounderConsole />} />
          {/* SURFACES Phase 10C: read-only surfaces unification view */}
          <Route path="/founder/surfaces" element={<FounderSurfaces />} />
          {/* OPERATOR Phase 11C: operator-mode posture (note: more
              specific /founder/operator/:user_id is registered above
              and continues to match for OperatorProfile). */}
          <Route path="/founder/operator" element={<FounderOperator />} />
          {/* LAUNCH Phase 12C: read-only public-launch readiness view */}
          <Route path="/founder/launch" element={<FounderLaunch />} />
          {/* IDENTITY Phase 13C: PIS / PISS dual-surface taxonomy.
              Lives as a child path under /founder/identity (Phase 8C).
              The literal Phase 13 spec asked for /founder/identity but
              that path is already bound to FounderIdentity (the Phase 8C
              identity-coherence layer); this child path coexists with it. */}
          <Route path="/founder/identity/pis-piss" element={<FounderPisPiss />} />
          {/* CATEGORY Phase 14C: Inferential Discipline System
              category definition + external-language guardrails.
              Sibling under /founder/identity/* alongside Phase 8C
              and Phase 13C. */}
          <Route path="/founder/identity/category" element={<FounderCategory />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
