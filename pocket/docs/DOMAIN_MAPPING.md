# Pocket — Custom Domain Mapping Runbook (`pocket.clarityos.dev`)

Maps the live Pocket Cloud Run service to its public custom domain so
visitors can reach the SPA at a memorable URL with a managed SSL
cert, instead of the long auto-generated `…run.app` URL.

Scope: this is a **runbook**, not a script — three of the five steps
require operator hands (Google Search Console verification + DNS
records + waiting for cert provisioning). The Claude-executable
parts (the gcloud command itself + post-mapping verification curls)
are inlined below.

## Why this matters

| Today | After this runbook |
|---|---|
| Pocket SPA URL: `https://clarityos-pocket-v0-3-736968277491.us-central1.run.app/` (long, opaque) | `https://pocket.clarityos.dev/` (shareable, brandable) |
| Browser-side `fetch` from SPA to `clarity-engine`: **CORS-blocked** (run.app origin not in allow-list) | **Works** — `https://pocket.clarityos.dev` was added to `CLARITYOS_CORS_ORIGINS` during the backend CORS card |
| `/login`, `/me`, `/clarify`, `/runs` calls: fail with `TypeError: Failed to fetch` in any real browser | All four screens become functional end-to-end |

The CORS unblock is the bigger half of the value — the URL change is
cosmetic by itself.

## Service inventory at time of writing

| Service | Region | Current revision | Image |
|---|---|---|---|
| `clarityos-pocket-v0-3` | `us-central1` | (see `gcloud run services describe`) | `us-central1-docker.pkg.dev/founding-os/cloud-run-source-deploy/clarityos-pocket-v0-3:<tag>` |
| `clarity-engine` | `us-central1` | `clarity-engine-00037-cqp` | (backend; CORS allow-list already includes `pocket.clarityos.dev`) |

Confirm with:

```bash
gcloud run services list --platform managed
```

---

## Prerequisites checklist

Before running step 3:

- [ ] `clarityos.dev` is a domain you own (registrar-side)
- [ ] You have admin access to the DNS zone for `clarityos.dev`
- [ ] You are signed into the same Google account that owns the
      `founding-os` GCP project
- [ ] `gcloud` is authenticated as that same account locally
      (`gcloud config list` shows the right account + project)
- [ ] The Pocket service is already deployed in `us-central1` (it is,
      since the v0.3.0 deploy card landed)

---

## Step 1 — Verify domain ownership in Google Search Console

**Why:** Cloud Run will refuse to create the domain mapping unless the
domain is verified, by the same Google account, in **Google Search
Console** (GSC). This is Google-wide policy — there is no
`gcloud`-only path around it.

**Actions (operator, in the browser):**

1. Open <https://search.google.com/search-console>.
2. Click **Add property** → **Domain** property type.
3. Enter `clarityos.dev` (the apex — verifying the apex covers all
   subdomains including `pocket.clarityos.dev`).
4. GSC will give you a TXT record value that looks like:
   `google-site-verification=<random-43-char-string>`
5. Add this TXT record at your DNS provider:

   | Type | Host | Value | TTL |
   |---|---|---|---|
   | TXT | `@` (apex) | `google-site-verification=...` | 300 (5 min) |

6. Wait for DNS propagation (usually 1–5 min for a fresh zone, can be
   up to the TTL of any pre-existing record).
7. Back in GSC, click **Verify**. You should see "Ownership
   verified".

**Verification command (run after GSC says verified):**

```bash
# Should return the verification TXT among any others
dig +short TXT clarityos.dev | grep google-site-verification
```

---

## Step 2 — Add the DNS CNAME for `pocket`

**Why:** Cloud Run domain mappings use a CNAME that points the
subdomain at Google's frontend (`ghs.googlehosted.com`). The
frontend then routes to the right service based on the host header.

**DNS record to add:**

| Type | Host | Value | TTL |
|---|---|---|---|
| CNAME | `pocket` (i.e. `pocket.clarityos.dev`) | `ghs.googlehosted.com.` | 300 |

> **Note:** the trailing dot in `ghs.googlehosted.com.` is the
> canonical FQDN form. Most DNS UIs accept either; if your provider
> normalises it, leave it as `ghs.googlehosted.com`.

**Verification command:**

```bash
dig +short CNAME pocket.clarityos.dev
# Expected: ghs.googlehosted.com.
```

If you get an empty response or a different value, the record hasn't
propagated yet. Wait 1–5 minutes and re-check.

---

## Step 3 — Create the Cloud Run domain mapping

**This is the only `gcloud` command in the runbook.** Run it from
any machine with `gcloud` authenticated against the `founding-os`
project.

```bash
gcloud run domain-mappings create \
    --service clarityos-pocket-v0-3 \
    --domain pocket.clarityos.dev \
    --region us-central1 \
    --platform managed
```

**Expected output (success):**

```
Mapping for [pocket.clarityos.dev] to service [clarityos-pocket-v0-3]
has been created.

Please add the following resource records to map your custom domain
to the service:
NAME          TYPE  DATA
pocket        CNAME ghs.googlehosted.com.
```

(If you already added the CNAME in step 2, you'll see this output
but the mapping is in flight — proceed to step 4.)

**Common failure modes and what they mean:**

| Error | Cause | Fix |
|---|---|---|
| `Domain ownership verified by another account` | A different Google account already owns the GSC verification for `clarityos.dev` | Re-verify in GSC under the same account that runs `gcloud`, OR transfer ownership |
| `PERMISSION_DENIED: The caller does not have permission` | gcloud auth account doesn't have `run.admin` on `founding-os` | `gcloud auth login` as the right account, OR grant the role |
| `The domain pocket.clarityos.dev is not verified` | Step 1 not completed | Go back to step 1; verify in GSC; then re-run |
| `ALREADY_EXISTS: Domain mapping for pocket.clarityos.dev already exists` | Someone already created this mapping (perhaps a previous attempt) | Use `gcloud run domain-mappings describe --domain pocket.clarityos.dev --region us-central1 --platform managed` to see what's there; then `delete` and re-create, or `update`, or leave alone |

---

## Step 4 — Wait for SSL cert provisioning

After step 3 succeeds, Google starts provisioning a managed SSL cert
for `pocket.clarityos.dev`. This is automatic and free; it just
takes time.

**Typical timing:**

- DNS propagation: 1–15 min (mostly already happened in step 2)
- Cert issuance: 15 min – 24 h (usually under an hour)
- Total: budget **up to a few hours** for the cert to go from
  `Provisioning` → `Active`

**Status check (run every few minutes):**

```bash
gcloud run domain-mappings describe \
    --domain pocket.clarityos.dev \
    --region us-central1 \
    --platform managed \
    --format='value(status.conditions[].type,status.conditions[].status,status.conditions[].message)'
```

You want to see something like:

```
DomainRoutable        True
CertificateProvisioned True
Ready                 True
```

If `CertificateProvisioned` stays `False` for more than a few hours,
check the `message` field — most common reasons are DNS
misconfiguration or unverified domain.

**Inline shortcut:**

```bash
# Quick "is the cert live yet" probe (returns 200 once everything
# is wired through; returns 526 / handshake error while
# provisioning):
curl -sI -o /dev/null -w "%{http_code}\n" https://pocket.clarityos.dev/
```

---

## Step 5 — Verify

Once `CertificateProvisioned = True`, run the full smoke set:

```bash
# 1. SPA shell loads
curl -i https://pocket.clarityos.dev/

# 2. Every route returns the same SPA shell (nginx fallback)
for path in /runtime /login /clarify /me /runs /landing /privacy /terms /nonexistent; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://pocket.clarityos.dev$path")
    echo "$code  $path"
done
# Expected: every line should print "200" — the nginx try_files
# fallback serves index.html for any unknown path so the SPA
# router can take over.

# 3. CORS is happy with the new origin
curl -i \
    -H "Origin: https://pocket.clarityos.dev" \
    https://clarity-engine-736968277491.us-central1.run.app/health
# Look for header:  Access-Control-Allow-Origin: https://pocket.clarityos.dev

# 4. CORS preflight is happy
curl -i -X OPTIONS \
    -H "Origin: https://pocket.clarityos.dev" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: X-Session-ID,Content-Type" \
    https://clarity-engine-736968277491.us-central1.run.app/me
# Look for:
#   Access-Control-Allow-Origin: https://pocket.clarityos.dev
#   Access-Control-Allow-Methods: GET, POST, OPTIONS
#   Access-Control-Allow-Headers: ... X-Session-ID ... Content-Type ...
#   Access-Control-Allow-Credentials: true
```

**Browser sanity check:**

1. Open `https://pocket.clarityos.dev/` in a fresh browser tab.
2. DevTools → Network → reload — every request should be 200.
3. Click **Sign in** in the nav.
4. Enter credentials; the POST to `/login` should succeed (was
   CORS-blocked on the `…run.app` URL before this runbook).
5. After login, `/me` should populate (real user info, not "Not
   signed in").
6. `/clarify` should accept text and return a JSON response from
   `/markov`.
7. `/runs` should list regression runs.
8. `/runtime` "Ping backend" should return the backend health
   payload.

If ALL of these work, the runbook is complete.

---

## Verification checklist (operator-facing)

Use this as a one-screen reference to confirm the work is done:

- [ ] **DNS:** `dig pocket.clarityos.dev CNAME` returns
      `ghs.googlehosted.com.`
- [ ] **DNS (verification):** `dig clarityos.dev TXT` includes the
      `google-site-verification=...` record
- [ ] **GSC:** `clarityos.dev` shows "Ownership verified" under the
      same Google account that runs gcloud
- [ ] **Domain mapping created:** `gcloud run domain-mappings list
      --region us-central1` includes `pocket.clarityos.dev` →
      `clarityos-pocket-v0-3`
- [ ] **DomainRoutable:** `True` in the describe output
- [ ] **CertificateProvisioned:** `True` in the describe output
- [ ] **Live HTTPS:** `curl https://pocket.clarityos.dev/` returns
      200 + the SPA shell
- [ ] **Deep links:** every Pocket route returns 200 from
      `pocket.clarityos.dev` (SPA fallback works)
- [ ] **CORS:** `/health` from the backend, with
      `Origin: https://pocket.clarityos.dev`, returns
      `Access-Control-Allow-Origin: https://pocket.clarityos.dev`
- [ ] **End-to-end:** /login → /me → /clarify → /runs all work in a
      real browser

---

## Rollback

If the mapping needs to be removed (e.g. you want to point the
subdomain somewhere else):

```bash
gcloud run domain-mappings delete \
    --domain pocket.clarityos.dev \
    --region us-central1 \
    --platform managed
```

This removes the mapping but does NOT delete the DNS CNAME — drop
that at your DNS provider too if you want the subdomain to stop
resolving to Google. The managed cert is removed automatically when
the mapping is deleted.

---

## Notes for the next domain

The same pattern works for any other Pocket-adjacent custom domain
(e.g. `cockpit.clarityos.dev` for the Node v0.2 web surface):

1. Verify the apex in GSC (one-time per apex domain — already done
   for `clarityos.dev` after this runbook)
2. Add a CNAME for the subdomain to `ghs.googlehosted.com`
3. `gcloud run domain-mappings create --service <SERVICE>
   --domain <SUBDOMAIN>.clarityos.dev --region us-central1
   --platform managed`
4. Add the new origin to `CLARITYOS_CORS_ORIGINS` on
   `clarity-engine` if the service does browser-side fetches
   against the backend
