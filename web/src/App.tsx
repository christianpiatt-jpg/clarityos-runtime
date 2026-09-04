import { Navigate, Route, Routes } from "react-router-dom";
import ErrorBoundary from "./components/ErrorBoundary";
import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import RequireAdmin from "./components/RequireAdmin";
import Home from "./routes/Home";
import Login from "./routes/Login";
import Operator from "./routes/Operator";
import OperatorConsole from "./routes/OperatorConsole"; // Card 40 — Engine V1 operator console (Phase-1)
import Sessions from "./routes/Sessions";
import Continuity from "./routes/Continuity";
import Markov from "./routes/Markov";
import System from "./routes/System";
import Vault from "./routes/Vault";
import Library from "./routes/Library";
import Timeline from "./routes/Timeline";
import Success from "./routes/Success";
import Cancel from "./routes/Cancel";
import Cockpit from "./routes/Cockpit";   // v28 — surface composite
import Elins from "./routes/Elins";       // v28 — ELINS feed + #G runner
import MembershipPage from "./routes/MembershipPage"; // v30 — Founding cohort + #G credits (+ the account, #141)
import FounderWaitlist from "./routes/FounderWaitlist"; // v32 — founder waitlist console
import Founder from "./routes/Founder";                 // v33 — founder console
import Dashboard from "./routes/Dashboard";             // v38 — ELINS dashboard
import OperatorProfile from "./routes/OperatorProfile"; // v39 — founder operator profile
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

/**
 * #145 -- TWO RAILS, ONE FLAG. CT-1 RULED 09-04: /founder is admin only.
 *
 * The route table has three tiers:
 *   PUBLIC     / /login /success /cancel
 *   MEMBER     RequireAuth -- the member's own stores (/vault /library
 *              /timeline), /membership (+ the account, #141), /cockpit,
 *              /personal-elins, /dashboard (the window, not the doors).
 *   OPERATOR   RequireAuth > RequireAdmin -- every other path. A member
 *              who types one is sent to /cockpit (RequireAdmin), never a
 *              refusal page; a signed-out visitor meets RequireAuth's CTA.
 *
 * ★★ RequireAdmin is UX, NOT SECURITY. The founder routes are gated
 * server-side (app._require_founder -> users_store.is_controller, 403
 * admin_only); the operator runtime routes are session-gated. A member who
 * reaches an operator path by some other route sees 403s, not privileged
 * data. The real boundary is the backend and stays there.
 *
 * /plans and /account fold into /membership (#141); /threads is /cockpit
 * (#144). All three are redirects, kept so a bookmark is not a 404.
 */
export default function App() {
  return (
    <ErrorBoundary label="Application error">
    <Routes>
      {/* /cockpit-v2 — kept as a REDIRECT rather than removed. It is the
          path every operator bookmarked while V2 was the experiment, and a
          dead bookmark is a support ticket. Chosen over deletion. */}
      <Route path="/cockpit-v2" element={<Navigate to="/cockpit" replace />} />
      {/* #144 -- /threads is the member cockpit. #141 -- /plans and
          /account live on /membership. Redirects, not 404s. */}
      <Route path="/threads" element={<Navigate to="/cockpit" replace />} />
      <Route path="/plans" element={<Navigate to="/membership" replace />} />
      <Route path="/account" element={<Navigate to="/membership" replace />} />

      {/* Surface 4 — v1 surface owns the full viewport.                 */}
      {/* Bypasses Layout so its cockpit chrome (topbar/rail/footer)    */}
      {/* doesn't nest inside the v1 surface's own chrome.              */}
      {/* v54-followup — /personal-elins follows the same pattern.       */}
      <Route element={<RequireAuth />}>
        {/* ★ /cockpit IS THE MEMBER PRODUCT. Swapped, not rewired: every
            existing pointer already says /cockpit (auth_magiclink
            DEFAULT_NEXT_PATH, [My Account], the magic link), so changing
            what is mounted lands all of them on V2 with no other edit.

            It sits HERE and not in the <Layout> block below, because
            CockpitV2 owns the full viewport and renders its own topbar --
            nesting it inside Layout would stack two sets of chrome. It is
            inside RequireAuth: V2's own login panel is a fallback, not the
            gate.

            This also ends V2's orphan status. Nothing linked to it, which
            is how 9fd1109 broke its chat send unnoticed. */}
        <Route path="/cockpit" element={<CockpitV2 />} />
        <Route path="/personal-elins" element={<PersonalElins />} />
        {/* v74 / Unit 84 — Founding 500 Subscription Gate. Owns the
            full viewport (Somatic canvas + 1px red boundary), so
            bypasses the cockpit chrome like /cockpit above. Auth
            required (post WordPress -> Stripe Checkout -> /auth/consume). */}
        <Route path="/founding500/confirm" element={<Unit84Layout />} />
      </Route>

      <Route element={<Layout />}>
        {/* Public */}
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        {/* Post-checkout landings. Stripe redirects here; both are
            unauthenticated — the buyer has paid but not yet clicked their
            magic link. */}
        <Route path="/success" element={<Success />} />
        <Route path="/cancel" element={<Cancel />} />

        {/* MEMBER -- the member's own stores (Storage Layer v1,
            server-authoritative), the membership + account page (v30 /
            #141), and the dashboard window (v38; server gates by the
            v28_surfaces flag, and its doors render only for the admin). */}
        <Route element={<RequireAuth />}>
          <Route path="/vault" element={<Vault />} />
          <Route path="/library" element={<Library />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/membership" element={<MembershipPage />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Route>

        {/* OPERATOR -- everything else, behind the flag. */}
        <Route element={<RequireAuth />}>
          <Route element={<RequireAdmin />}>
            {/* #143 -- /system carries the per-browser API-base override.
                It was public; it is the admin's. */}
            <Route path="/system" element={<System />} />
            <Route path="/operator" element={<Operator />} />
            {/* Card 40 — Engine V1 Operator Console (Phase-1 diagnostic panel). */}
            <Route path="/operator/console" element={<OperatorConsole />} />
            <Route path="/markov" element={<Markov />} />
            {/* bridges — external iframe surface. Layout-wrapped so the
                cockpit chrome (rail + status bar) stays available for
                navigation away. */}
            <Route path="/iframe" element={<Iframe />} />
            {/* v61 / Unit 44 — Operator session runtime UI. The operator_id
                passed to start_session is the authed user. */}
            <Route path="/session" element={<Session />} />
            {/* v63 / Unit 47 — Read-only session history viewer. */}
            <Route path="/session/history" element={<SessionHistory />} />
            {/* v63 / Unit 48 — Read-only vault inspector ("Runtime Vault" on
                the rail, #34). /operator-vault not /vault because the v1
                storage layer already owns /vault for the member's file
                vault — different concept, different storage layer. */}
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
            {/* These two used to work without auth ("local-only"). They are
                operator instruments; they sit with the rest. */}
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/continuity" element={<Continuity />} />
            {/* ★ V1 lives on here for the admin account. NOT PORTED -- it
                keeps working exactly as it did, and panels graduate to V2
                one at a time. */}
            <Route path="/admin/cockpit" element={<Cockpit />} />
            {/* v28 — ELINS feed + #G runner. */}
            <Route path="/elins" element={<Elins />} />

            {/* v32 — Founder waitlist deep-link. v33 — Founder console at
                /founder composes waitlist + DMs + membership ops + ELINS +
                #cmt. Every /founder/* handler answers 403 admin_only to a
                non-controller session. */}
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
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </ErrorBoundary>
  );
}
