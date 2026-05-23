# A20-R — Form Semantics & Error Surfaces

Status: shipped (commit on `feature/v0.2.0-web-surface`).

## What this is

A20-R adds a **server-authored form-semantics layer** on top of
A13-R (parsing), A14-R (validation), and A15 (function-typed
schemas), and wires the A19-R progressive-enhancement
fetch-and-replace path to accept HTML error fragments inline.

Everything is additive. No new server endpoints, no new
classifier branches, no SPA touch. Validation logic is
unchanged — A20-R just exposes it through a single ergonomic
entry point and gives it a server-rendered HTML surface.

## Philosophy

- **Server HTML is the source of truth.** Errors are computed
  server-side and rendered server-side. The client never owns
  the error state.
- **Validation is a first-class request question.** Asking
  "what's wrong with this submission?" should be one call, not
  a multi-step orchestration. `collectFormErrors(request)`
  delivers that.
- **Errors render through the same template engine as
  everything else.** No special error renderer, no new
  framework. The `errorFragment.html` template is just an HTML
  file the loader knows how to find (A3 conventions).
- **Progressive enhancement respects the no-JS baseline.** With
  JS off, forms submit natively and the server renders the full
  page with errors. With JS on, the same server-rendered
  fragment swaps into the page inline. Same HTML, same
  contract, two surfaces.

## File map

| Path | Role |
|---|---|
| `web/src/surface/forms/types.ts` | `FormFieldError`, `FormErrorBag`, `FormResult<T>`, `toFieldErrorList` helper. |
| `web/src/surface/forms/errors.ts` | `collectFormErrors(request)`, `renderFormErrors(bag)`, `EMPTY_FORM_ERRORS` constant. |
| `web/src/surface/forms/index.ts` | Barrel: re-exports `validateForm`, types, both helpers. |
| `web/templates/v0.2/errorFragment.html` | Server-rendered `<ul class="form-errors">` fragment template. |
| `web/src/client/enhance.ts` | Updated fetch-and-replace: content-type-based response handling (HTML → replace; non-HTML → fall back). |

## Server-side API

### `collectFormErrors(request)`

```ts
import { collectFormErrors } from "../forms";

const bag = await collectFormErrors(req);
if (Object.keys(bag.errors).length > 0) {
  // validation failed — render the error fragment and return
  // it as the response body
  return {
    status:  422,
    headers: { "content-type": "text/html; charset=utf-8" },
    body:    renderFormErrors(bag),
  };
}
```

Auto-orchestrates:
1. `parseFormBody(request.body)` (A13-R)
2. `resolveView(request)` → view definition (A2)
3. `resolveViewSchema(def.schema, fields)` (A14-R + A15)
4. `validateForm(fields, schema)` (A14-R)
5. Returns `{errors: result.errors}` as a `FormErrorBag`.

Pass-through (returns `EMPTY_FORM_ERRORS`) for:
- Non-string body (multipart, null, etc.)
- Unknown view
- View without a schema
- Schema function that returns `undefined` (e.g., terminal
  wizard step from A15)

### `renderFormErrors(bag)`

```ts
import { renderFormErrors } from "../forms";

const html = renderFormErrors({
  errors: { name: "Required.", email: "Invalid email address." },
});
// → '<ul class="form-errors">
//      <li data-field="name">Required.</li>
//      <li data-field="email">Invalid email address.</li>
//    </ul>'
```

- Both `field` (the data attribute) and `message` (the text)
  are HTML-escaped at the boundary.
- Empty bag → empty `<ul>` (no `<li>`s).
- Iteration order matches the bag's `Object.entries()` order,
  which mirrors schema declaration order — byte-stable.
- Uses the existing template engine and the `errorFragment`
  template; no new rendering path.

### `FormResult<T>`

For handlers that want to express success-or-failure at the
type level:

```ts
import type { FormResult } from "../forms";

interface UserInput { name: string; email: string }

async function handle(req): Promise<FormResult<UserInput>> {
  const bag = await collectFormErrors(req);
  if (Object.keys(bag.errors).length > 0) {
    return { ok: false, errors: bag };
  }
  return { ok: true, values: { name: "...", email: "..." } };
}
```

The compiler then enforces that `result.values` is only
accessible when `result.ok === true`, and `result.errors` only
when `result.ok === false`.

## Client-side behavior change

A19-R's fetch-and-replace handler branched on HTTP status:
- 2xx → replace target
- non-2xx → fall back to native submit

A20-R branches on Content-Type:
- HTML response (any status) → replace target
- Non-HTML response OR network failure → fall back to native submit

This lets a 4xx-with-HTML-error-fragment render inline as
inline validation errors, instead of triggering a full-page
reload. A 200-with-JSON still falls back (rare; this path is
for HTML rendering). A 500-with-HTML still replaces (the server
can speak HTML; we trust the HTML).

Content-Type detection is case-insensitive and tolerates
charset suffixes (`text/html; charset=utf-8` → HTML).

## Integration pattern

A typical form view + handler pairing:

```ts
// Server-side handler (custom view)
import {
  collectFormErrors,
  renderFormErrors,
} from "../forms";

async function handleUserForm(req) {
  const bag = await collectFormErrors(req);
  if (Object.keys(bag.errors).length > 0) {
    return {
      status:  422,
      headers: { "content-type": "text/html; charset=utf-8" },
      body:    renderFormErrors(bag),
    };
  }
  // ... success path ...
}
```

```html
<!-- View template -->
<form method="POST"
      action="/web-surface/v0.2/user_form"
      data-enhance="fetch"
      data-fragment-target="#errors">
  <input name="name">
  <input name="email">
  <button type="submit">Save</button>
</form>
<div id="errors"></div>
```

With JS: submit → fetch → server returns `<ul class="form-errors">`
→ swaps into `#errors`. No reload.

Without JS: submit → native POST → server returns the same
fragment as part of a full page → user sees the same errors,
in the same place, with a page reload.

## What's NOT here

- No new server endpoints. `collectFormErrors` is a helper for
  view code, not a route.
- No CSRF. Future card.
- No client-side validation. The client trusts what the server
  says; that's the whole point of "server HTML as source of
  truth".
- No form-state persistence across redirects. A future PRG
  (post-redirect-get) card can layer that on top.

## Tests

Server-side: 23 tests in `web/src/surface/__tests__/formErrors.test.ts`.

- Types: `EMPTY_FORM_ERRORS` shape, `toFieldErrorList` order,
  `FormResult` discriminator narrowing.
- `collectFormErrors`: valid form, invalid form, missing
  required, unknown view, view without schema, A15
  function-schema (step-based wizard pattern), non-string
  body, buffer body, no-mutation, declaration-order keys.
- `renderFormErrors`: empty bag, populated bag, XSS escape on
  message + field name, order preservation.
- Determinism: byte-identical across 5 renders, no input
  mutation.
- Barrel: `validateForm` + `ValidationSchema` callable through
  `forms/index.ts`.

Client-side: 11 tests in `web/src/client/__tests__/formEnhanceErrors.test.ts`.

- 422 + text/html → replace target.
- 400 + text/html → replace target.
- 500 + text/html → replace target (content-type wins over
  status).
- 422 + application/json → fall back.
- 500 + text/plain → fall back.
- 200 + application/json → fall back.
- Missing content-type header → fall back.
- 200 + text/html (A19-R happy path) → preserved.
- Network failure → fall back (A19-R behaviour preserved).
- Charset suffix detected (`text/html; charset=utf-8`).
- Uppercase content-type detected (case-insensitive).
