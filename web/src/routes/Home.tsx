// routes/Home.tsx — public landing page (v32).
//
// LEGACY: superseded by WordPress marketing surface per v74 / Unit 84
// agent-mesh stack resolution (WordPress = marketing + signup funnel,
// React = operator portal + Subscription Gate). Retained temporarily
// for reference and as a fallback while the WordPress migration
// settles. New public-surface work should land in
// /wp-content/themes/clarityos/ — not here.
//
// Sections:
//   1. Hero — what ClarityOS is
//   2. Founding Cohort — pricing, cap, perks
//   3. Capabilities — identity wrapper, trust-centered partner, vault, #c, #G, macro-ELINS
//   4. Timeline — May 15 launch + waitlist availability
//   5. Trust / privacy — local-first, metadata-only cloud
//   6. Call to action — "Join the Founding Cohort" or "Join the Waitlist"
//
// The CTA flips to "Join the Waitlist" when /public/cohort_status reports
// is_full: true. A small ClarityOS-style operator-shortcut row stays at the
// bottom for already-authenticated users.

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  isAuthed,
  publicCohortStatus,
  type V32CohortStatus,
} from "../lib/api";
import WaitlistForm from "../components/public/WaitlistForm";

export default function Home() {
  const [cohort, setCohort] = useState<V32CohortStatus | null>(null);
  const [cohortError, setCohortError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    publicCohortStatus()
      .then((r) => { if (active) setCohort(r); })
      .catch((e: unknown) => {
        if (active) setCohortError(e instanceof Error ? e.message : String(e));
      });
    return () => { active = false; };
  }, []);

  const isFull = cohort?.is_full === true;
  const remaining = cohort?.remaining;
  const authed = isAuthed();

  return (
    <div className="public-home" style={{ maxWidth: 760, margin: "0 auto" }}>
      <Hero isFull={isFull} remaining={remaining} />
      <FoundingCohort isFull={isFull} cohort={cohort} cohortError={cohortError} />
      <Capabilities />
      <Timeline isFull={isFull} />
      <Trust />
      <CallToAction isFull={isFull} />
      {authed && <OperatorShortcuts />}
    </div>
  );
}

// ---------- Sections -------------------------------------------------------

function Hero({ isFull, remaining }: { isFull: boolean; remaining: number | null | undefined }) {
  return (
    <section className="panel" style={{ padding: 24, marginBottom: 16 }}>
      <h1 style={{ margin: 0, fontSize: 28, lineHeight: 1.2 }}>ClarityOS</h1>
      <p
        style={{
          marginTop: 8,
          fontSize: 16,
          lineHeight: 1.5,
          color: "var(--os-text-secondary, #555)",
        }}
      >
        A cognitive operating system. Clarity about the forces shaping outcomes —
        not summaries, not advice. Local-first. Trust-centered. Yours.
      </p>
      {isFull ? (
        <div style={{ marginTop: 12, fontSize: 13, color: "#922" }}>
          Founding 500 cohort is currently full. Waitlist is open.
        </div>
      ) : typeof remaining === "number" ? (
        <div style={{ marginTop: 12, fontSize: 13, color: "var(--os-text-secondary, #555)" }}>
          {remaining} of 500 Founding seats remaining.
        </div>
      ) : null}
    </section>
  );
}

function FoundingCohort({
  isFull,
  cohort,
  cohortError,
}: {
  isFull: boolean;
  cohort: V32CohortStatus | null;
  cohortError: string | null;
}) {
  return (
    <Section title="Founding Cohort">
      <ul style={listStyle}>
        <Bullet>
          <strong>500-member cap.</strong>{" "}
          {cohort
            ? `${cohort.active_count} active, ${cohort.cap ?? "—"} cap.`
            : cohortError
              ? <span style={{ color: "#922" }}>(could not load fill stats: {cohortError})</span>
              : "Loading fill stats…"}
        </Bullet>
        <Bullet>
          <strong>$50 / month, locked for life</strong> — until you cancel.
          Cancellation forfeits the lock; reactivation pays the full price.
        </Bullet>
        <Bullet>
          <strong>Full price after the cohort: $150 / month.</strong>{" "}
          Founders pay $50 forever; everyone else joins at $150.
        </Bullet>
        <Bullet>
          <strong>Direct founder access.</strong> Real-time email and a private
          channel into product decisions.
        </Bullet>
        <Bullet>
          <strong>Participation in testing and evolution.</strong> Founders see
          new layers first and shape what ships.
        </Bullet>
      </ul>
      {isFull && (
        <div
          style={{
            marginTop: 12,
            padding: 8,
            background: "#fff8e1",
            border: "1px solid #f3d57a",
            fontSize: 13,
            borderRadius: 4,
          }}
        >
          The cohort is full. You can join the waitlist below; we contact people
          in order as spots open.
        </div>
      )}
    </Section>
  );
}

function Capabilities() {
  return (
    <Section title="Core capabilities">
      <ul style={listStyle}>
        <Bullet>
          <strong>Identity wrapper.</strong> Captures and reflects how you
          actually think — not a persona, not a profile.
        </Bullet>
        <Bullet>
          <strong>Trust-centered clarity partner.</strong> Powered by
          Emotional Physics and Langbridg. Surfaces the forces shaping a
          situation; never tells you what to do.
        </Bullet>
        <Bullet>
          <strong>Local vault.</strong> Notes, sessions, transcripts —
          stored on-device and yours alone.
        </Bullet>
        <Bullet>
          <strong>#c cloud engine.</strong> Sends only metadata to the
          cloud. No content leaves your machine without explicit action.
        </Bullet>
        <Bullet>
          <strong>#G personal ELINS.</strong> A private, deterministic
          scenario engine running over your own neighborhoods. Scenario
          text is never persisted in the cloud.
        </Bullet>
        <Bullet>
          <strong>Macro-ELINS.</strong> Three short structural reports per
          week on the wider environment. Delivered to your feed at 05:00
          local.
        </Bullet>
      </ul>
    </Section>
  );
}

function Timeline({ isFull }: { isFull: boolean }) {
  return (
    <Section title="Timeline">
      <ul style={listStyle}>
        <Bullet>
          <strong>Founding Cohort opens May 15.</strong>{" "}
          {isFull ? "(currently full)" : "Seats are claimed in the order they're paid for."}
        </Bullet>
        <Bullet>
          <strong>Waitlist is active.</strong> Join now and we'll reach out
          before the cohort opens — and again if a spot opens up later.
        </Bullet>
      </ul>
    </Section>
  );
}

function Trust() {
  return (
    <Section title="Trust & privacy">
      <ul style={listStyle}>
        <Bullet>
          <strong>Local-first.</strong> Sessions, vault entries, and
          transcripts never leave your machine.
        </Bullet>
        <Bullet>
          <strong>No content stored in the cloud.</strong> The cloud sees
          metadata only — counts, timestamps, neighborhood ids. Never the
          content itself.
        </Bullet>
        <Bullet>
          <strong>You can audit it.</strong> The cockpit's envelope viewer
          shows every layer the runtime has of you, at any time.
        </Bullet>
      </ul>
    </Section>
  );
}

function CallToAction({ isFull }: { isFull: boolean }) {
  return (
    <Section
      title={isFull ? "Join the Waitlist" : "Join the Founding Cohort"}
    >
      <p style={{ margin: 0, marginBottom: 12, fontSize: 14, lineHeight: 1.5 }}>
        {isFull
          ? (
            "The Founding 500 is full right now. Drop your email and we'll let you know when a spot opens."
          )
          : (
            "Drop your email and we'll reach out before the cohort opens on May 15. No account is created."
          )}
      </p>
      <WaitlistForm cohortFull={isFull} />
    </Section>
  );
}

function OperatorShortcuts() {
  // Render only when authed — pre-existing operators land on the public
  // home, see the marketing material, and still have their cockpit links.
  return (
    <Section title="Operator shortcuts">
      <div className="row" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Link to="/cockpit" className="btn">COCKPIT</Link>
        <Link to="/membership" className="btn btn-secondary">MEMBERSHIP</Link>
        <Link to="/elins" className="btn btn-secondary">ELINS</Link>
        <Link to="/operator" className="btn btn-secondary">OPERATOR</Link>
      </div>
    </Section>
  );
}

// ---------- Reusable bits --------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      className="panel"
      style={{
        padding: 16,
        marginBottom: 16,
        background: "var(--os-surface, #fafafa)",
        border: "1px solid var(--os-border, #ddd)",
        borderRadius: 6,
      }}
    >
      <h2 style={{ margin: 0, marginBottom: 8, fontSize: 18 }}>{title}</h2>
      {children}
    </section>
  );
}

function Bullet({ children }: { children: React.ReactNode }) {
  return <li style={{ marginBottom: 6, lineHeight: 1.5 }}>{children}</li>;
}

const listStyle: React.CSSProperties = {
  margin: 0,
  paddingLeft: 18,
  fontSize: 14,
};
