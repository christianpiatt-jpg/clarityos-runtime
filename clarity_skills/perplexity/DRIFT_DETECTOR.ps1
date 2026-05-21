# DRIFT_DETECTOR.ps1 — v2.0.0 (Agent Kernel aware)
#
# Compares the current state of clarity_skills/perplexity/ against
# BASELINE_STATE.json and reports drift.
#
# Output:
#   DRIFT: NONE                 (exit 0)
#   DRIFT: DETECTED              (exit 1)
#     - <itemized reason>
#     - <itemized reason>
#
# v1.0.0 detections (preserved):
#   * Skill .md or .zip hash divergence from baseline.
#   * Governance file hash divergence from baseline.
#   * Anchor file (MANIFEST.json, README.md) hash divergence.
#   * Missing files that the baseline lists.
#   * Unexpected files in the folder that the baseline does not list.
#   * manifest_version drift between MANIFEST.json and baseline.
#   * BUILD_VERSION drift between C:\ClarityOS_Code\BUILD_VERSION and baseline.
#
# v1.2.0 additions (preserved):
#   * SKILL_TAXONOMY.md presence + hash via governance_files.
#   * schema_version match.
#   * governance.taxonomy_file = "SKILL_TAXONOMY.md".
#   * Per-skill version, md_sha256, zip_sha256, category, governance_version,
#     baseline_hash in MANIFEST.json against baseline.
#
# v2.0.0 additions:
#   * Agent .md hash divergence — iterates baseline.agents (new top-level
#     block, parallel to baseline.skills).
#   * AGENT_SPEC_TEMPLATE.md and AGENT_TAXONOMY.md tracked via
#     governance_files (taxonomy and template are governance files).
#   * governance.agent_template_file = "AGENT_SPEC_TEMPLATE.md".
#   * governance.agent_taxonomy_file = "AGENT_TAXONOMY.md".
#   * Per-agent version, md_sha256, category, governance_version,
#     agent_kernel_version, baseline_hash in MANIFEST.json against baseline.
#   * Per-agent skills_used must reference skills present in MANIFEST.json.
#   * Agent .md files are added to the expected-files list (no .zip — agents
#     do not have zip bundles).
#
# Strict mode: ANY divergence is reported as drift. When you make
# authorized changes, regenerate BASELINE_STATE.json after the release
# settles so the next run reports DRIFT: NONE.

$ErrorActionPreference = "Stop"

$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$baselinePath = Join-Path $folder "BASELINE_STATE.json"

if (-not (Test-Path $baselinePath)) {
  Write-Output "DRIFT: DETECTED"
  Write-Output " - BASELINE_STATE.json not found at $baselinePath"
  exit 1
}

$b = Get-Content -Raw -LiteralPath $baselinePath | ConvertFrom-Json
$drift = New-Object System.Collections.Generic.List[string]

function Get-Sha256ForFile($path) {
  if (-not (Test-Path -LiteralPath $path)) { return $null }
  return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLower()
}

# --- Skills (file-level) ---
foreach ($skillName in $b.skills.PSObject.Properties.Name) {
  $expected = $b.skills.$skillName
  $mdPath  = Join-Path $folder "$skillName.md"
  $zipPath = Join-Path $folder "$skillName.zip"

  $mdHash  = Get-Sha256ForFile $mdPath
  $zipHash = Get-Sha256ForFile $zipPath

  if ($null -eq $mdHash) {
    $drift.Add("$skillName.md missing")
  } elseif ($mdHash -ne $expected.hash_md) {
    $drift.Add("$skillName.md hash mismatch (baseline=$($expected.hash_md), current=$mdHash)")
  }

  if ($null -eq $zipHash) {
    $drift.Add("$skillName.zip missing")
  } elseif ($zipHash -ne $expected.hash_zip) {
    $drift.Add("$skillName.zip hash mismatch (baseline=$($expected.hash_zip), current=$zipHash)")
  }
}

# --- Agents (file-level, v2.0.0) ---
if ($null -ne $b.agents) {
  foreach ($agentName in $b.agents.PSObject.Properties.Name) {
    $expected = $b.agents.$agentName
    $mdPath = Join-Path $folder "$agentName.md"

    $mdHash = Get-Sha256ForFile $mdPath

    if ($null -eq $mdHash) {
      $drift.Add("$agentName.md missing (agent)")
    } elseif ($mdHash -ne $expected.hash_md) {
      $drift.Add("$agentName.md hash mismatch (baseline=$($expected.hash_md), current=$mdHash)")
    }
  }
}

# --- Governance files (incl. SKILL_TAXONOMY.md, AGENT_SPEC_TEMPLATE.md,
#                       AGENT_TAXONOMY.md under v2.0.0) ---
foreach ($fname in $b.governance_files.PSObject.Properties.Name) {
  $expected = $b.governance_files.$fname
  $path = Join-Path $folder $fname
  $hash = Get-Sha256ForFile $path

  if ($null -eq $hash) {
    $drift.Add("$fname missing (governance file)")
  } elseif ($hash -ne $expected.hash) {
    $drift.Add("$fname hash mismatch (governance file changed without baseline regeneration; baseline=$($expected.hash), current=$hash)")
  }
}

# --- Anchor files (MANIFEST.json, README.md) ---
foreach ($fname in $b.anchor_files.PSObject.Properties.Name) {
  $expected = $b.anchor_files.$fname
  $path = Join-Path $folder $fname
  $hash = Get-Sha256ForFile $path

  if ($null -eq $hash) {
    $drift.Add("$fname missing (anchor file)")
  } elseif ($hash -ne $expected.hash) {
    $drift.Add("$fname hash mismatch (anchor file modified; baseline=$($expected.hash), current=$hash)")
  }
}

# --- manifest schema + per-skill + per-agent metadata ---
$manifestPath = Join-Path $folder "MANIFEST.json"
if (Test-Path -LiteralPath $manifestPath) {
  try {
    $m = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
  } catch {
    $drift.Add("MANIFEST.json failed to parse as JSON: $($_.Exception.Message)")
    $m = $null
  }

  if ($null -ne $m) {
    if ($m.manifest_version -ne $b.manifest_version) {
      $drift.Add("MANIFEST.json manifest_version drift: baseline=$($b.manifest_version), current=$($m.manifest_version)")
    }
    if ($null -ne $m.schema_version -and $null -ne $b.schema_version -and $m.schema_version -ne $b.schema_version) {
      $drift.Add("MANIFEST.json schema_version drift: baseline=$($b.schema_version), current=$($m.schema_version)")
    }
    if ($null -ne $m.governance) {
      if ($m.governance.taxonomy_file -ne "SKILL_TAXONOMY.md") {
        $drift.Add("MANIFEST.json governance.taxonomy_file = '$($m.governance.taxonomy_file)', expected 'SKILL_TAXONOMY.md'")
      }
      # v2.0.0: agent_template_file + agent_taxonomy_file in governance block
      if ($null -ne $b.agents -and $m.governance.agent_template_file -ne "AGENT_SPEC_TEMPLATE.md") {
        $drift.Add("MANIFEST.json governance.agent_template_file = '$($m.governance.agent_template_file)', expected 'AGENT_SPEC_TEMPLATE.md'")
      }
      if ($null -ne $b.agents -and $m.governance.agent_taxonomy_file -ne "AGENT_TAXONOMY.md") {
        $drift.Add("MANIFEST.json governance.agent_taxonomy_file = '$($m.governance.agent_taxonomy_file)', expected 'AGENT_TAXONOMY.md'")
      }
    }

    # Per-skill manifest field consistency with baseline
    foreach ($s in $m.skills) {
      $bs = $b.skills.$($s.name)
      if ($null -eq $bs) {
        $drift.Add("manifest skill '$($s.name)' is not in BASELINE_STATE.json")
        continue
      }
      if ($s.version -ne $bs.version) {
        $drift.Add("$($s.name) version drift: baseline=$($bs.version), manifest=$($s.version)")
      }
      if ($null -ne $bs.hash_md -and $s.md_sha256 -ne $bs.hash_md) {
        $drift.Add("$($s.name) manifest md_sha256 differs from baseline.hash_md (baseline=$($bs.hash_md), manifest=$($s.md_sha256))")
      }
      if ($null -ne $bs.hash_zip -and $s.zip_sha256 -ne $bs.hash_zip) {
        $drift.Add("$($s.name) manifest zip_sha256 differs from baseline.hash_zip (baseline=$($bs.hash_zip), manifest=$($s.zip_sha256))")
      }
      if ($null -ne $bs.category -and $null -ne $s.category -and $s.category -ne $bs.category) {
        $drift.Add("$($s.name) category drift: baseline=$($bs.category), manifest=$($s.category)")
      }
      if ($null -ne $bs.governance_version -and $null -ne $s.governance_version -and $s.governance_version -ne $bs.governance_version) {
        $drift.Add("$($s.name) governance_version drift: baseline=$($bs.governance_version), manifest=$($s.governance_version)")
      }
      if ($null -ne $bs.baseline_hash -and $null -ne $s.baseline_hash -and $s.baseline_hash -ne $bs.baseline_hash) {
        $drift.Add("$($s.name) baseline_hash drift (immutable): baseline=$($bs.baseline_hash), manifest=$($s.baseline_hash)")
      }
    }

    # Per-agent manifest field consistency with baseline (v2.0.0)
    if ($null -ne $m.agents) {
      foreach ($a in $m.agents) {
        $ba = $null
        if ($null -ne $b.agents) { $ba = $b.agents.$($a.name) }
        if ($null -eq $ba) {
          $drift.Add("manifest agent '$($a.name)' is not in BASELINE_STATE.json")
          continue
        }
        if ($a.version -ne $ba.version) {
          $drift.Add("agent $($a.name) version drift: baseline=$($ba.version), manifest=$($a.version)")
        }
        if ($null -ne $ba.hash_md -and $a.md_sha256 -ne $ba.hash_md) {
          $drift.Add("agent $($a.name) md_sha256 differs from baseline (baseline=$($ba.hash_md), manifest=$($a.md_sha256))")
        }
        if ($null -ne $ba.category -and $null -ne $a.category -and $a.category -ne $ba.category) {
          $drift.Add("agent $($a.name) category drift: baseline=$($ba.category), manifest=$($a.category)")
        }
        if ($null -ne $ba.governance_version -and $null -ne $a.governance_version -and $a.governance_version -ne $ba.governance_version) {
          $drift.Add("agent $($a.name) governance_version drift: baseline=$($ba.governance_version), manifest=$($a.governance_version)")
        }
        if ($null -ne $ba.agent_kernel_version -and $null -ne $a.agent_kernel_version -and $a.agent_kernel_version -ne $ba.agent_kernel_version) {
          $drift.Add("agent $($a.name) agent_kernel_version drift: baseline=$($ba.agent_kernel_version), manifest=$($a.agent_kernel_version)")
        }
        if ($null -ne $ba.baseline_hash -and $null -ne $a.baseline_hash -and $a.baseline_hash -ne $ba.baseline_hash) {
          $drift.Add("agent $($a.name) baseline_hash drift (immutable): baseline=$($ba.baseline_hash), manifest=$($a.baseline_hash)")
        }
      }
    }
  }
}

# --- BUILD_VERSION ---
$bvPath = "C:\ClarityOS_Code\BUILD_VERSION"
if (Test-Path -LiteralPath $bvPath) {
  $bv = (Get-Content -Raw -LiteralPath $bvPath).Trim()
  if ($bv -ne $b.build_version) {
    $drift.Add("BUILD_VERSION drift: baseline=$($b.build_version), current=$bv")
  }
} else {
  $drift.Add("BUILD_VERSION file not found at $bvPath")
}

# --- Unexpected files in folder ---
$expectedFiles = New-Object System.Collections.Generic.List[string]
foreach ($skillName in $b.skills.PSObject.Properties.Name) {
  [void]$expectedFiles.Add("$skillName.md")
  [void]$expectedFiles.Add("$skillName.zip")
}
if ($null -ne $b.agents) {
  foreach ($agentName in $b.agents.PSObject.Properties.Name) {
    [void]$expectedFiles.Add("$agentName.md")
  }
}
foreach ($fname in $b.governance_files.PSObject.Properties.Name) { [void]$expectedFiles.Add($fname) }
foreach ($fname in $b.anchor_files.PSObject.Properties.Name)     { [void]$expectedFiles.Add($fname) }
[void]$expectedFiles.Add("BASELINE_STATE.json")

$actualFiles = Get-ChildItem -LiteralPath $folder -File | ForEach-Object { $_.Name }
foreach ($f in $actualFiles) {
  if ($expectedFiles -notcontains $f) {
    $drift.Add("unexpected file in folder: $f (not listed in BASELINE_STATE.json)")
  }
}

# --- Output ---
if ($drift.Count -eq 0) {
  Write-Output "DRIFT: NONE"
  exit 0
} else {
  Write-Output "DRIFT: DETECTED"
  foreach ($line in $drift) { Write-Output " - $line" }
  exit 1
}
