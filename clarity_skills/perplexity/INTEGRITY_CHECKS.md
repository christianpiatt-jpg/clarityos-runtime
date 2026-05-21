# Skill Library Integrity Checks

This document defines the verification procedure for everything in
`clarity_skills/perplexity/`. Run these checks before committing any
new or revised skill, and after any tooling change that touches the
library.

All commands assume PowerShell with the working directory set to
`C:\ClarityOS_Code\clarity_skills\perplexity\` unless otherwise noted.

---

## A. Hash Verification Procedure

`MANIFEST.json` records two SHA256 hashes per skill: `md_sha256` (over
the source `.md`) and `zip_sha256` (over the upload bundle). Both
hashes must match the on-disk files exactly.

### Compute SHA256 for a single skill

```powershell
$name = "<skill-name>"
$md   = (Get-FileHash -LiteralPath "$name.md"  -Algorithm SHA256).Hash.ToLower()
$zip  = (Get-FileHash -LiteralPath "$name.zip" -Algorithm SHA256).Hash.ToLower()
"md  : $md"
"zip : $zip"
```

Paste the resulting values into the skill's `MANIFEST.json` entry
under `md_sha256` and `zip_sha256`.

### Verify the entire library against `MANIFEST.json`

This block computes the actual hashes for every skill listed in the
manifest and compares them to the recorded values:

```powershell
$folder = "C:\ClarityOS_Code\clarity_skills\perplexity"
$m = Get-Content -Raw -LiteralPath (Join-Path $folder "MANIFEST.json") |
       ConvertFrom-Json
foreach ($s in $m.skills) {
  $mdActual  = (Get-FileHash -LiteralPath (Join-Path $folder $s.filename) `
                 -Algorithm SHA256).Hash.ToLower()
  $zipActual = (Get-FileHash -LiteralPath (Join-Path $folder $s.zip_filename) `
                 -Algorithm SHA256).Hash.ToLower()
  $mdOk  = ($mdActual  -eq $s.md_sha256)
  $zipOk = ($zipActual -eq $s.zip_sha256)
  $status = if ($mdOk -and $zipOk) { "OK  " } else { "FAIL" }
  Write-Output "$status  $($s.name) v$($s.version)  md=$mdOk  zip=$zipOk"
}
```

### Expected output

If the library is intact, every line begins with `OK`:

```
OK    clarity-narrative-litigation v1.0.0  md=True  zip=True
OK    clarity-contradictions-extractor v1.0.0  md=True  zip=True
OK    clarity-timeline-mapper v1.0.0  md=True  zip=True
```

A `FAIL` line means the on-disk file diverges from the manifest.
Either regenerate the affected artifact or update the manifest — do
**not** commit a `FAIL` state.

### Verify a zip's `SKILL.md` matches its source `.md`

Independently of the manifest, you can confirm any zip's payload is
byte-identical to its source `.md`:

```powershell
$name = "<skill-name>"
$tmp  = Join-Path $env:TEMP ("verify_" + [guid]::NewGuid())
Expand-Archive -LiteralPath "$name.zip" -DestinationPath $tmp -Force
$inZip  = (Get-FileHash -LiteralPath (Join-Path $tmp "SKILL.md") `
             -Algorithm SHA256).Hash.ToLower()
$source = (Get-FileHash -LiteralPath "$name.md" `
             -Algorithm SHA256).Hash.ToLower()
"in_zip : $inZip"
"source : $source"
"match  : $($inZip -eq $source)"
Remove-Item $tmp -Recurse -Force
```

`match : True` is the required outcome.

---

## B. Structural Checks

Run these against every new or revised skill before zipping.

### 1. YAML frontmatter validity

The file must start with a `---` line, contain `name:` and
`description:` fields, and end with another `---` before the markdown
body.

```powershell
$name = "<skill-name>"
$content = Get-Content -Raw -LiteralPath "$name.md"
if ($content -match '(?s)^---\s*\r?\n(.*?)\r?\n---\s*\r?\n') {
  $front = $Matches[1]
  $hasName = ($front -match '(?m)^name:\s*\S')
  $hasDesc = ($front -match '(?m)^description:\s*\S|^description:\s*>\s*$')
  "frontmatter parses: True"
  "name field present: $hasName"
  "description present: $hasDesc"
} else {
  "FAIL: no parseable frontmatter block"
}
```

### 2. `name` is lowercase, hyphens only

```powershell
$name = "<skill-name>"
if ($name -cmatch '^[a-z0-9-]+$') { "name format OK" } else { "FAIL: name format" }
```

The same name must appear in the `name:` field of the frontmatter and
in the filenames (`<name>.md` and `<name>.zip`).

### 3. `description` contains trigger phrases

The `description` field is the matcher Perplexity uses to decide
whether to invoke the skill. It must contain explicit triggers —
phrases like `Use when…`, `Analyze…`, `Extract…`, `Build…`, `Identify…`,
`Map…`.

```powershell
$content = Get-Content -Raw -LiteralPath "<skill-name>.md"
if ($content -match '(?ms)^description:.*?(Use when|Analyze|Extract|Build|Identify|Map|Review|Classify)') {
  "trigger phrase present"
} else {
  "FAIL: description lacks an explicit trigger"
}
```

### 4. File size under 10 MB

```powershell
$md  = (Get-Item "<skill-name>.md").Length
$zip = (Get-Item "<skill-name>.zip").Length
"md  : $md bytes  ($([math]::Round($md/1MB,3)) MB)"
"zip : $zip bytes ($([math]::Round($zip/1MB,3)) MB)"
if ($md -lt 10MB -and $zip -lt 10MB) { "size OK" } else { "FAIL: size" }
```

### 5. `SKILL.md` at the root of the zip

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$arc = [System.IO.Compression.ZipFile]::OpenRead("<skill-name>.zip")
$entries = $arc.Entries | ForEach-Object { $_.FullName }
$arc.Dispose()
if ($entries.Count -eq 1 -and $entries[0] -eq "SKILL.md") {
  "zip layout OK (single SKILL.md at root)"
} else {
  "FAIL: zip contains $($entries.Count) entries: $($entries -join ', ')"
}
```

### 6. Schema 1.3.0 — required `input_shape`, `output_shape`, `dependencies`

As of schema 1.3.0, every skill manifest entry MUST include:

- `input_shape` — non-empty string describing the input shape the skill consumes.
- `output_shape` — non-empty string describing the output shape the skill produces.
- `dependencies` — list (may be empty `[]`) of skill `name` strings that this skill depends on.

```powershell
$m = Get-Content -Raw -LiteralPath "MANIFEST.json" | ConvertFrom-Json
$skillNames = $m.skills | ForEach-Object { $_.name }
foreach ($s in $m.skills) {
  $hasInput  = $s.PSObject.Properties.Name -contains 'input_shape'
  $hasOutput = $s.PSObject.Properties.Name -contains 'output_shape'
  $hasDeps   = $s.PSObject.Properties.Name -contains 'dependencies'

  $okInput  = $hasInput  -and -not [string]::IsNullOrWhiteSpace($s.input_shape)
  $okOutput = $hasOutput -and -not [string]::IsNullOrWhiteSpace($s.output_shape)
  $okDeps   = $hasDeps  # presence only; null = empty array (PowerShell scalar collapse)

  $depsResolve = $true
  if ($hasDeps -and $null -ne $s.dependencies) {
    foreach ($d in $s.dependencies) {
      if ($skillNames -notcontains $d) { $depsResolve = $false }
    }
  }

  $allOk = $okInput -and $okOutput -and $okDeps -and $depsResolve
  Write-Output "$($s.name) : input=$okInput output=$okOutput deps=$okDeps deps_resolve=$depsResolve : $(if ($allOk) {'OK'} else {'FAIL'})"
}
```

Validation rules:

- `input_shape` and `output_shape` must be non-empty strings (whitespace-only is treated as empty and fails).
- `dependencies` must be present as a property. The value may be `null` (PowerShell-side representation of a JSON empty array `[]`) or an array of strings. Items, if any, must reference skills that exist in `m.skills`.
- A skill missing or empty in any of these three fields FAILS the self-test and is treated as a governance violation.

---

## C. Contamination Checks

Skills are Layer 1 — general-case only. They must not carry any Layer 2
material. These checks catch the common contamination paths.

### 1. No PII

A skill must not contain:

- Names of individuals
- Email addresses, phone numbers, postal addresses
- Date-of-birth, SSN, agency case numbers
- Anything tied to a real person

Quick scan for typical PII shapes:

```powershell
$file = "<skill-name>.md"
"--- SSN-like ---"
Select-String -LiteralPath $file -Pattern '\b\d{3}-\d{2}-\d{4}\b'
"--- phone-like ---"
Select-String -LiteralPath $file -Pattern '\b\d{3}[-.]\d{3}[-.]\d{4}\b'
"--- email-like ---"
Select-String -LiteralPath $file -Pattern '\b[\w.+-]+@[\w-]+\.[\w.-]+\b'
```

Any hits must be removed or generalized before commit.

### 2. No personal-envelope content

A skill must not reference Layer 2 artifacts: the `VA_LITIGATION`
project, the `MSJ_OPPOSITION` thread, named parties, contested matters,
or anything specific to one engagement.

```powershell
Select-String -LiteralPath "<skill-name>.md" `
  -Pattern '(VA_LITIGATION|MSJ_OPPOSITION|DOJ filing|specific case|our matter|the petitioner|the respondent named)'
```

Generic mentions of agencies as **categories** (e.g. "agency
decisions", "VA handbooks", "MSPB procedure") are acceptable. Specific
case material is not.

### 3. No case-specific material

A skill must describe a **method**. If the file only makes sense to
someone who already knows the facts of a particular matter, it has
slipped from method into case content.

Three quick heuristics:

- Could this skill be uploaded to a fresh Perplexity workspace with no
  context, and still be useful? If no, it is too specific.
- Are the examples generic shapes (`Event A`, `Section II claims X`),
  or are they real fragments? They must be generic.
- Does the skill reference a contested timeline, a specific filing
  date, or a specific decision number? If yes, those belong in the
  particular-case workspace, not in the skill.

### 4. General-case-only assertion

After running the above checks, confirm the file's `description` and
body would apply equally to any matter, not just the current one. The
skill is the *method*; the case is the *input* to the method.

---

## Pre-Commit Verification Suite

Run this entire block before committing a new or revised skill:

```powershell
$folder = "C:\ClarityOS_Code\clarity_skills\perplexity"
$name   = "<skill-name>"
$mdPath  = Join-Path $folder "$name.md"
$zipPath = Join-Path $folder "$name.zip"

# 1. Hashes
$md  = (Get-FileHash -LiteralPath $mdPath  -Algorithm SHA256).Hash.ToLower()
$zip = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLower()
"md_sha256  = $md"
"zip_sha256 = $zip"

# 2. Structural
$content = Get-Content -Raw -LiteralPath $mdPath
if ($content -match '(?s)^---\s*\r?\n.*?\r?\n---') { "frontmatter OK" } else { "FAIL frontmatter" }
if ($name -cmatch '^[a-z0-9-]+$') { "name format OK" } else { "FAIL name format" }
if ((Get-Item $mdPath ).Length -lt 10MB) { "md size OK" }  else { "FAIL md size" }
if ((Get-Item $zipPath).Length -lt 10MB) { "zip size OK" } else { "FAIL zip size" }

# 3. Zip layout
Add-Type -AssemblyName System.IO.Compression.FileSystem
$arc = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$entries = $arc.Entries | ForEach-Object { $_.FullName }
$arc.Dispose()
if ($entries.Count -eq 1 -and $entries[0] -eq "SKILL.md") {
  "zip layout OK"
} else {
  "FAIL zip layout: $($entries -join ', ')"
}

# 4. PII / contamination quick scan (any hit = investigate)
"--- contamination scan ---"
Select-String -LiteralPath $mdPath `
  -Pattern '\b\d{3}-\d{2}-\d{4}\b|@[\w.-]+\.[\w.-]+|VA_LITIGATION|MSJ_OPPOSITION|the petitioner|the respondent named'
```

Paste the resulting `md_sha256` and `zip_sha256` into the new skill's
manifest entry. The release is complete only when every check above
returns a non-`FAIL` line, the contamination scan returns no hits
(or only false positives you have inspected), and `MANIFEST.json`
reflects the actual files.

After committing, re-run the **library-wide** verification (§ A) to
confirm every skill in the library still returns `OK`.
