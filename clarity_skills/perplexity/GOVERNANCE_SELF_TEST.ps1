# GOVERNANCE_SELF_TEST.ps1 -- v2.1.0 (Schema 1.3.0 enforcement)
#
# Verifies the governance layer is internally consistent. Meta-check on
# whether the governance layer itself can do its job, including the
# Agent Kernel (introduced at governance v2.0.0) and the Schema 1.3.0
# per-skill enforcement (mandatory input_shape, output_shape, dependencies).
#
# Output:
#   GOVERNANCE SELF-TEST: OK     (exit 0)
#     - <per-check OK lines>
#   GOVERNANCE SELF-TEST: FAIL (<n> failures)  (exit 1)
#     - <per-check OK / FAIL lines>
#
# v1.0.0 + v1.2.0 + v2.0.0 checks (preserved, with one softened):
#   1. Canonical governance files exist (7 with agent kernel: VERSIONING,
#      INTEGRITY_CHECKS, SKILL_TEMPLATE, CREATE_NEW_SKILL_INSTRUCTIONS,
#      SKILL_TAXONOMY, AGENT_SPEC_TEMPLATE, AGENT_TAXONOMY).
#   2. All canonical files referenced in MANIFEST.json governance block.
#   3. manifest_version is semver.
#   4. Integrity tooling can read every governance file.
#   5. BASELINE_STATE.json exists and tracks every canonical governance
#      file with a version field.
#   7. SOFTENED at v2.1.0: schema_version is present and semver. The
#      v2.0.0 equality check (manifest_version == schema_version) is
#      removed -- the two version fields legitimately track different
#      things from schema 1.3.0 onward (manifest tracks structural
#      schema; schema_version tracks per-skill content schema).
#   8. Each skill has all schema 1.2.0+ required fields.
#   9. Each skill's category is in SKILL_TAXONOMY.
#  10. Each skill's governance_version is semver.
#  11. Each skill's baseline_hash is valid SHA256.
#  12. CREATE_NEW_SKILL_INSTRUCTIONS.md references SKILL_TAXONOMY.md.
#  13. SKILL_TEMPLATE.md frontmatter includes schema 1.2.0+ fields.
#  14. Each agent in MANIFEST.json has all schema 2.0.0 required fields.
#  15. Each agent's category is in AGENT_TAXONOMY.
#  16. Each agent's governance_version + agent_kernel_version are semver.
#  17. Each agent's baseline_hash is valid SHA256.
#  18. Each agent's skills_used references skills present in m.skills.
#  19. AGENT_SPEC_TEMPLATE.md includes schema 2.0.0 agent fields.
#
# v2.1.0 additions (Schema 1.3.0):
#  20. Each skill has non-empty input_shape (schema 1.3.0).
#  21. Each skill has non-empty output_shape (schema 1.3.0).
#  22. Each skill has dependencies field (may be empty list); items, if
#      any, must reference skills present in m.skills.
#  23. SKILL_TEMPLATE.md frontmatter includes input_shape, output_shape,
#      and dependencies (schema 1.3.0).

$ErrorActionPreference = "Stop"

$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$results = New-Object System.Collections.Generic.List[string]

$canonicalFiles = @(
  "VERSIONING.md",
  "INTEGRITY_CHECKS.md",
  "SKILL_TEMPLATE.md",
  "CREATE_NEW_SKILL_INSTRUCTIONS.md",
  "SKILL_TAXONOMY.md",
  "AGENT_SPEC_TEMPLATE.md",
  "AGENT_TAXONOMY.md"
)

# --- Check 1: canonical files exist ---
$allExist = $true
foreach ($f in $canonicalFiles) {
  if (-not (Test-Path -LiteralPath (Join-Path $folder $f))) {
    [void]$results.Add("FAIL: missing canonical governance file $f")
    $allExist = $false
  }
}
if ($allExist) {
  [void]$results.Add("OK: all seven canonical governance files present")
}

# --- Check 2: manifest references ---
$manifestPath = Join-Path $folder "MANIFEST.json"
$m = $null
if (-not (Test-Path -LiteralPath $manifestPath)) {
  [void]$results.Add("FAIL: MANIFEST.json missing")
} else {
  try {
    $m = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
  } catch {
    [void]$results.Add("FAIL: MANIFEST.json failed to parse: $($_.Exception.Message)")
    $m = $null
  }
  if ($null -ne $m) {
    if ($null -eq $m.governance) {
      [void]$results.Add("FAIL: MANIFEST.json has no top-level governance block")
    } else {
      $g = $m.governance
      $expected = [ordered]@{
        "versioning_file"        = "VERSIONING.md"
        "integrity_checks_file"  = "INTEGRITY_CHECKS.md"
        "pipeline_file"          = "CREATE_NEW_SKILL_INSTRUCTIONS.md"
        "template_file"          = "SKILL_TEMPLATE.md"
        "taxonomy_file"          = "SKILL_TAXONOMY.md"
        "agent_template_file"    = "AGENT_SPEC_TEMPLATE.md"
        "agent_taxonomy_file"    = "AGENT_TAXONOMY.md"
      }
      $allRefOk = $true
      foreach ($key in $expected.Keys) {
        if ($g.$key -ne $expected[$key]) {
          [void]$results.Add("FAIL: governance.$key = '$($g.$key)', expected '$($expected[$key])'")
          $allRefOk = $false
        }
      }
      if ($allRefOk) {
        [void]$results.Add("OK: all seven canonical files referenced in manifest governance block")
      }
    }

    # --- Check 3: manifest_version is semver ---
    if ($m.manifest_version -match '^\d+\.\d+\.\d+$') {
      [void]$results.Add("OK: manifest_version = $($m.manifest_version) (semver)")
    } else {
      [void]$results.Add("FAIL: manifest_version not semver: '$($m.manifest_version)'")
    }

    # --- Check 7 (v2.1.0 SOFTENED): schema_version is present and semver ---
    if ($null -eq $m.schema_version) {
      [void]$results.Add("FAIL: schema_version field missing from manifest")
    } elseif ($m.schema_version -notmatch '^\d+\.\d+\.\d+$') {
      [void]$results.Add("FAIL: schema_version not semver: '$($m.schema_version)'")
    } else {
      $note = if ($m.schema_version -ne $m.manifest_version) {
        " (intentionally divergent from manifest_version=$($m.manifest_version) -- schema 1.3.0+ tracks per-skill schema separately)"
      } else { "" }
      [void]$results.Add("OK: schema_version = $($m.schema_version) (semver)$note")
    }

    # --- Check 8: each skill has schema 1.2.0+ required fields ---
    $requiredSkillFields = @("name","version","filename","zip_filename","description","md_sha256","zip_sha256","md_bytes","zip_bytes","category","capabilities","limitations","governance_version","baseline_hash")
    $allFieldsOk = $true
    foreach ($s in $m.skills) {
      $missing = @()
      foreach ($f in $requiredSkillFields) {
        if ($null -eq $s.$f) { $missing += $f }
      }
      if ($missing.Count -gt 0) {
        [void]$results.Add("FAIL: skill '$($s.name)' missing required fields: $($missing -join ', ')")
        $allFieldsOk = $false
      }
    }
    if ($allFieldsOk) {
      [void]$results.Add("OK: all skills have schema 1.2.0+ required fields")
    }

    # --- Check 9: skill categories are in SKILL_TAXONOMY ---
    $taxonomyPath = Join-Path $folder "SKILL_TAXONOMY.md"
    if (Test-Path -LiteralPath $taxonomyPath) {
      $taxBody = Get-Content -Raw -LiteralPath $taxonomyPath
      $taxNames = New-Object System.Collections.Generic.List[string]
      $rx = [regex]::new('(?m)^\|\s*\*\*([A-Z][\w \-/]+)\*\*\s*\|')
      foreach ($mm in $rx.Matches($taxBody)) {
        [void]$taxNames.Add($mm.Groups[1].Value.Trim())
      }
      if ($taxNames.Count -eq 0) {
        [void]$results.Add("FAIL: no category names parsed from SKILL_TAXONOMY.md")
      } else {
        $unknownCat = $false
        foreach ($s in $m.skills) {
          if ($null -ne $s.category -and ($taxNames -notcontains $s.category)) {
            [void]$results.Add("FAIL: skill '$($s.name)' category '$($s.category)' not in SKILL_TAXONOMY")
            $unknownCat = $true
          }
        }
        if (-not $unknownCat) {
          [void]$results.Add("OK: all skill categories are valid SKILL_TAXONOMY entries ($($taxNames.Count) categories)")
        }
      }
    } else {
      [void]$results.Add("FAIL: SKILL_TAXONOMY.md not found")
    }

    # --- Check 10: skill governance_version is semver ---
    $allGvOk = $true
    foreach ($s in $m.skills) {
      if ($null -ne $s.governance_version -and ($s.governance_version -notmatch '^\d+\.\d+\.\d+$')) {
        [void]$results.Add("FAIL: skill '$($s.name)' governance_version not semver")
        $allGvOk = $false
      }
    }
    if ($allGvOk) {
      [void]$results.Add("OK: all skill governance_version fields are valid semver")
    }

    # --- Check 11: skill baseline_hash is valid SHA256 ---
    $allBhOk = $true
    foreach ($s in $m.skills) {
      if ($null -ne $s.baseline_hash -and ($s.baseline_hash -notmatch '^[a-f0-9]{64}$')) {
        [void]$results.Add("FAIL: skill '$($s.name)' baseline_hash is not 64 lowercase hex chars")
        $allBhOk = $false
      }
    }
    if ($allBhOk) {
      [void]$results.Add("OK: all skill baseline_hash fields are valid SHA256")
    }

    # --- v2.1.0 Check 20: skill input_shape present + non-empty ---
    $allInputOk = $true
    foreach ($s in $m.skills) {
      $hasField = $s.PSObject.Properties.Name -contains 'input_shape'
      if (-not $hasField) {
        [void]$results.Add("FAIL: skill '$($s.name)' missing input_shape (schema 1.3.0 required)")
        $allInputOk = $false
      } elseif ([string]::IsNullOrWhiteSpace([string]$s.input_shape)) {
        [void]$results.Add("FAIL: skill '$($s.name)' input_shape is empty (schema 1.3.0 required)")
        $allInputOk = $false
      }
    }
    if ($allInputOk) {
      [void]$results.Add("OK: all skills have non-empty input_shape (schema 1.3.0)")
    }

    # --- v2.1.0 Check 21: skill output_shape present + non-empty ---
    $allOutputOk = $true
    foreach ($s in $m.skills) {
      $hasField = $s.PSObject.Properties.Name -contains 'output_shape'
      if (-not $hasField) {
        [void]$results.Add("FAIL: skill '$($s.name)' missing output_shape (schema 1.3.0 required)")
        $allOutputOk = $false
      } elseif ([string]::IsNullOrWhiteSpace([string]$s.output_shape)) {
        [void]$results.Add("FAIL: skill '$($s.name)' output_shape is empty (schema 1.3.0 required)")
        $allOutputOk = $false
      }
    }
    if ($allOutputOk) {
      [void]$results.Add("OK: all skills have non-empty output_shape (schema 1.3.0)")
    }

    # --- v2.1.0 Check 22: skill dependencies field present + items resolve ---
    $skillNames = $m.skills | ForEach-Object { $_.name }
    $allDepsOk = $true
    foreach ($s in $m.skills) {
      $hasField = $s.PSObject.Properties.Name -contains 'dependencies'
      if (-not $hasField) {
        [void]$results.Add("FAIL: skill '$($s.name)' missing dependencies field (schema 1.3.0 required)")
        $allDepsOk = $false
        continue
      }
      # null = empty array (PS scalar collapse). Otherwise must be enumerable.
      if ($null -ne $s.dependencies) {
        foreach ($d in $s.dependencies) {
          if ($skillNames -notcontains $d) {
            [void]$results.Add("FAIL: skill '$($s.name)' dependencies references unknown skill '$d'")
            $allDepsOk = $false
          }
        }
      }
    }
    if ($allDepsOk) {
      [void]$results.Add("OK: all skills have dependencies field; all referenced skills resolve (schema 1.3.0)")
    }

    # --- Check 14 (v2.0.0): each agent has schema 2.0.0 required fields ---
    if ($null -ne $m.agents) {
      $requiredAgentFields = @("name","version","filename","description","md_sha256","md_bytes","category","capabilities","limitations","skills_used","behavioral_profile","activation_triggers","output_shape","governance_version","agent_kernel_version","baseline_hash")
      $allAgentFieldsOk = $true
      foreach ($a in $m.agents) {
        $missing = @()
        foreach ($f in $requiredAgentFields) {
          if ($null -eq $a.$f) { $missing += $f }
        }
        if ($missing.Count -gt 0) {
          [void]$results.Add("FAIL: agent '$($a.name)' missing required schema 2.0.0 fields: $($missing -join ', ')")
          $allAgentFieldsOk = $false
        }
      }
      if ($allAgentFieldsOk) {
        [void]$results.Add("OK: all agents have schema 2.0.0 required fields")
      }

      # --- Check 15: agent categories are in AGENT_TAXONOMY ---
      $agentTaxPath = Join-Path $folder "AGENT_TAXONOMY.md"
      if (Test-Path -LiteralPath $agentTaxPath) {
        $atBody = Get-Content -Raw -LiteralPath $agentTaxPath
        $atNames = New-Object System.Collections.Generic.List[string]
        $rx = [regex]::new('(?m)^\|\s*\*\*([A-Z][\w \-/]+)\*\*\s*\|')
        foreach ($mm in $rx.Matches($atBody)) {
          [void]$atNames.Add($mm.Groups[1].Value.Trim())
        }
        if ($atNames.Count -eq 0) {
          [void]$results.Add("FAIL: no category names parsed from AGENT_TAXONOMY.md")
        } else {
          $unknownAgentCat = $false
          foreach ($a in $m.agents) {
            if ($null -ne $a.category -and ($atNames -notcontains $a.category)) {
              [void]$results.Add("FAIL: agent '$($a.name)' category '$($a.category)' not in AGENT_TAXONOMY")
              $unknownAgentCat = $true
            }
          }
          if (-not $unknownAgentCat) {
            [void]$results.Add("OK: all agent categories are valid AGENT_TAXONOMY entries ($($atNames.Count) categories)")
          }
        }
      } else {
        [void]$results.Add("FAIL: AGENT_TAXONOMY.md not found")
      }

      # --- Check 16: agent governance_version + agent_kernel_version are semver ---
      $agentVerOk = $true
      foreach ($a in $m.agents) {
        if ($null -ne $a.governance_version -and ($a.governance_version -notmatch '^\d+\.\d+\.\d+$')) {
          [void]$results.Add("FAIL: agent '$($a.name)' governance_version not semver")
          $agentVerOk = $false
        }
        if ($null -ne $a.agent_kernel_version -and ($a.agent_kernel_version -notmatch '^\d+\.\d+\.\d+$')) {
          [void]$results.Add("FAIL: agent '$($a.name)' agent_kernel_version not semver")
          $agentVerOk = $false
        }
      }
      if ($agentVerOk) {
        [void]$results.Add("OK: all agent version fields are valid semver")
      }

      # --- Check 17: agent baseline_hash is valid SHA256 ---
      $agentBhOk = $true
      foreach ($a in $m.agents) {
        if ($null -ne $a.baseline_hash -and ($a.baseline_hash -notmatch '^[a-f0-9]{64}$')) {
          [void]$results.Add("FAIL: agent '$($a.name)' baseline_hash is not 64 lowercase hex chars")
          $agentBhOk = $false
        }
      }
      if ($agentBhOk) {
        [void]$results.Add("OK: all agent baseline_hash fields are valid SHA256")
      }

      # --- Check 18: agent skills_used references existing skills ---
      $allSkillsRefOk = $true
      foreach ($a in $m.agents) {
        if ($null -ne $a.skills_used) {
          foreach ($skillRef in $a.skills_used) {
            if ($skillNames -notcontains $skillRef) {
              [void]$results.Add("FAIL: agent '$($a.name)' references skill '$skillRef' which is not in MANIFEST.json skills")
              $allSkillsRefOk = $false
            }
          }
        }
      }
      if ($allSkillsRefOk) {
        [void]$results.Add("OK: all agent skills_used entries reference existing skills")
      }
    } else {
      [void]$results.Add("OK: no agents present in manifest (Agent Kernel block empty)")
    }
  }
}

# --- Check 4: integrity tooling can read governance files ---
$readOk = $true
foreach ($f in $canonicalFiles) {
  $path = Join-Path $folder $f
  if (Test-Path -LiteralPath $path) {
    try {
      $null = Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop
    } catch {
      [void]$results.Add("FAIL: cannot hash $f ($($_.Exception.Message))")
      $readOk = $false
    }
  }
}
if ($readOk) {
  [void]$results.Add("OK: integrity tooling can hash all governance files")
}

# --- Check 5: baseline tracks governance files with versions ---
$baselinePath = Join-Path $folder "BASELINE_STATE.json"
if (-not (Test-Path -LiteralPath $baselinePath)) {
  [void]$results.Add("FAIL: BASELINE_STATE.json missing")
} else {
  try {
    $bjson = Get-Content -Raw -LiteralPath $baselinePath | ConvertFrom-Json
  } catch {
    [void]$results.Add("FAIL: BASELINE_STATE.json failed to parse: $($_.Exception.Message)")
    $bjson = $null
  }
  if ($null -ne $bjson) {
    if ($null -eq $bjson.governance_files) {
      [void]$results.Add("FAIL: BASELINE_STATE.json has no governance_files block")
    } else {
      $gfNames = $bjson.governance_files.PSObject.Properties.Name
      $missing = @()
      foreach ($f in $canonicalFiles) {
        if ($gfNames -notcontains $f) { $missing += $f }
        else {
          $entry = $bjson.governance_files.$f
          if ($null -eq $entry.version -or $entry.version -notmatch '^\d+\.\d+\.\d+$') {
            $missing += "$f (version field missing or not semver)"
          }
        }
      }
      if ($missing.Count -eq 0) {
        [void]$results.Add("OK: all canonical governance files versioned in BASELINE_STATE.json")
      } else {
        [void]$results.Add("FAIL: not properly versioned in baseline: $($missing -join ', ')")
      }
    }
  }
}

# --- Check 12: instructions reference taxonomy ---
$instrPath = Join-Path $folder "CREATE_NEW_SKILL_INSTRUCTIONS.md"
if (Test-Path -LiteralPath $instrPath) {
  $instrBody = Get-Content -Raw -LiteralPath $instrPath
  if ($instrBody -match 'SKILL_TAXONOMY\.md') {
    [void]$results.Add("OK: CREATE_NEW_SKILL_INSTRUCTIONS.md references SKILL_TAXONOMY.md")
  } else {
    [void]$results.Add("FAIL: CREATE_NEW_SKILL_INSTRUCTIONS.md does not reference SKILL_TAXONOMY.md")
  }
}

# --- Check 13: skill template includes new schema fields ---
$tmplPath = Join-Path $folder "SKILL_TEMPLATE.md"
if (Test-Path -LiteralPath $tmplPath) {
  $tmplBody = Get-Content -Raw -LiteralPath $tmplPath
  $required = @('category', 'capabilities', 'limitations', 'governance_version')
  $missing = @()
  foreach ($field in $required) {
    if ($tmplBody -notmatch "(?m)^${field}:") { $missing += $field }
  }
  if ($missing.Count -eq 0) {
    [void]$results.Add("OK: SKILL_TEMPLATE.md frontmatter includes all schema 1.2.0 fields")
  } else {
    [void]$results.Add("FAIL: SKILL_TEMPLATE.md frontmatter missing fields: $($missing -join ', ')")
  }

  # --- v2.1.0 Check 23: SKILL_TEMPLATE.md frontmatter includes schema 1.3.0 fields ---
  $required13 = @('input_shape', 'output_shape', 'dependencies')
  $missing13 = @()
  foreach ($field in $required13) {
    if ($tmplBody -notmatch "(?m)^${field}:") { $missing13 += $field }
  }
  if ($missing13.Count -eq 0) {
    [void]$results.Add("OK: SKILL_TEMPLATE.md frontmatter includes all schema 1.3.0 fields")
  } else {
    [void]$results.Add("FAIL: SKILL_TEMPLATE.md frontmatter missing schema 1.3.0 fields: $($missing13 -join ', ')")
  }
}

# --- v2.0.0 Check 19: agent template includes the schema 2.0.0 agent fields ---
$agentTmplPath = Join-Path $folder "AGENT_SPEC_TEMPLATE.md"
if (Test-Path -LiteralPath $agentTmplPath) {
  $agentTmplBody = Get-Content -Raw -LiteralPath $agentTmplPath
  $required = @('category', 'capabilities', 'limitations', 'skills_used', 'behavioral_profile', 'activation_triggers', 'output_shape', 'governance_version', 'agent_kernel_version')
  $missing = @()
  foreach ($field in $required) {
    if ($agentTmplBody -notmatch "(?m)^${field}:") { $missing += $field }
  }
  if ($missing.Count -eq 0) {
    [void]$results.Add("OK: AGENT_SPEC_TEMPLATE.md frontmatter includes all schema 2.0.0 agent fields")
  } else {
    [void]$results.Add("FAIL: AGENT_SPEC_TEMPLATE.md frontmatter missing fields: $($missing -join ', ')")
  }
}

# --- Final output ---
$failCount = ($results | Where-Object { $_ -like "FAIL:*" }).Count

if ($failCount -eq 0) {
  Write-Output "GOVERNANCE SELF-TEST: OK"
  Write-Output ""
  foreach ($r in $results) { Write-Output "  $r" }
  exit 0
} else {
  Write-Output "GOVERNANCE SELF-TEST: FAIL ($failCount failure$(if ($failCount -ne 1){'s'}))"
  Write-Output ""
  foreach ($r in $results) { Write-Output "  $r" }
  exit 1
}
