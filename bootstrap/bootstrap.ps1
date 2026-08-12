# Bootstrap this machine (Windows) from the claude-config repo.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap\bootstrap.ps1
#
# Idempotent: safe to re-run after pulling changes. Backs up ~\.claude.json and
# ~\.claude\settings.json before touching them.
#
# Options:
#   -ProjectsRoot <path>   where your repos live      (default: %USERPROFILE%\projects)
#   -SkipVenv              don't build the google-ads-write venv
#   -WhatIfOnly            report what would change, write nothing

param(
  [string]$ProjectsRoot = (Join-Path $env:USERPROFILE 'projects'),
  [switch]$SkipVenv,
  [switch]$WhatIfOnly
)

$ErrorActionPreference = 'Stop'
$root       = Split-Path -Parent $PSScriptRoot
$claudeDir  = Join-Path $env:USERPROFILE '.claude'
$claudeJson = Join-Path $env:USERPROFILE '.claude.json'
$settings   = Join-Path $claudeDir 'settings.json'
$stamp      = Get-Date -Format 'yyyyMMdd-HHmmss'
$todo       = New-Object System.Collections.Generic.List[string]

function Info($m) { Write-Host "  $m" }
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "  ! $m" -ForegroundColor Yellow }

function Strip-Comments($obj) {
  # Drop the _comment documentation keys before anything reaches a real config file.
  $out = [ordered]@{}
  foreach ($p in $obj.PSObject.Properties) {
    if ($p.Name -eq '_comment') { continue }
    $out[$p.Name] = $p.Value
  }
  $out
}

function Save-Json($path, $obj) {
  if ($WhatIfOnly) { Info "would write $path"; return }
  $json = $obj | ConvertTo-Json -Depth 100
  # Round-trip check: never leave a half-written config behind.
  $null = $json | ConvertFrom-Json
  $tmp = "$path.tmp"
  Set-Content -Path $tmp -Value $json -Encoding UTF8
  Move-Item -Path $tmp -Destination $path -Force
}

# --------------------------------------------------------------------------
Step 'Prerequisites'
foreach ($t in @(
  @{n='claude'; hint='https://claude.com/claude-code'},
  @{n='npx';    hint='install Node.js LTS - needed by the WordPress/Elementor servers'},
  @{n='py';     hint='install Python 3.11+ from python.org - needed by serenite-ads-write'},
  @{n='pipx';   hint='py -m pip install --user pipx - needed by serenite-ads'},
  @{n='gcloud'; hint='https://cloud.google.com/sdk/docs/install - needed by both Google Ads servers'}
)) {
  if (Get-Command $t.n -ErrorAction SilentlyContinue) { Info "$($t.n) found" }
  else { Warn "$($t.n) MISSING - $($t.hint)"; $todo.Add("install $($t.n): $($t.hint)") }
}

# --------------------------------------------------------------------------
Step 'Skills'
$skillsDst = Join-Path $claudeDir 'skills'
if (-not $WhatIfOnly) { New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null }
Get-ChildItem (Join-Path $root 'skills') -Directory | ForEach-Object {
  if ($WhatIfOnly) { Info "would copy skill $($_.Name)" }
  else {
    Copy-Item $_.FullName -Destination $skillsDst -Recurse -Force
    Info "installed skill $($_.Name)"
  }
}

# --------------------------------------------------------------------------
Step 'settings.json'
$shared = Strip-Comments (Get-Content (Join-Path $root 'settings\settings.shared.json') -Raw | ConvertFrom-Json)

$credPath = Join-Path $root 'secrets\credentials.json'
$credEnv  = @{}
if (Test-Path $credPath) {
  $cred = Get-Content $credPath -Raw | ConvertFrom-Json
  foreach ($p in $cred.env.PSObject.Properties) {
    if ([string]::IsNullOrWhiteSpace($p.Value)) { Warn "credentials.json: $($p.Name) is empty" }
    $credEnv[$p.Name] = $p.Value
  }
  if ([string]::IsNullOrWhiteSpace($cred.googleAds.GOOGLE_ADS_DEVELOPER_TOKEN)) {
    $todo.Add('fill googleAds.GOOGLE_ADS_DEVELOPER_TOKEN in secrets\credentials.json (or set the env var)')
  }
} else {
  Warn "no secrets\credentials.json - copy it from the Mac; the WordPress servers will 401 without it"
  $todo.Add('copy secrets\credentials.json from the Mac over a secure channel')
}

$existing = if (Test-Path $settings) { Get-Content $settings -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
$merged = [ordered]@{}
foreach ($p in $existing.PSObject.Properties) { $merged[$p.Name] = $p.Value }   # keep machine-local keys
foreach ($k in $shared.Keys)                  { $merged[$k]      = $shared[$k] } # shared wins

$env_ = [ordered]@{}
if ($existing.env) { foreach ($p in $existing.env.PSObject.Properties) { $env_[$p.Name] = $p.Value } }
foreach ($k in $credEnv.Keys) { $env_[$k] = $credEnv[$k] }
$merged['env'] = $env_

if (Test-Path $settings) { Copy-Item $settings "$settings.bak-$stamp" }
Save-Json $settings ([pscustomobject]$merged)
Info "merged $($shared.Keys.Count) shared keys and $($credEnv.Count) credentials"

# --------------------------------------------------------------------------
Step 'google-ads-write venv'
$serverDir = Join-Path $root 'servers\google-ads-write'
$venvPy    = Join-Path $serverDir '.venv\Scripts\python.exe'
if ($SkipVenv) { Info 'skipped (-SkipVenv)' }
elseif ($WhatIfOnly) { Info "would build venv at $serverDir\.venv" }
elseif (Test-Path $venvPy) { Info 'venv already present' }
elseif (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  Warn 'python not found - skipping venv'; $todo.Add('install Python, then re-run bootstrap')
} else {
  & py -3 -m venv (Join-Path $serverDir '.venv')
  & $venvPy -m pip install --quiet --upgrade pip
  & $venvPy -m pip install --quiet -e $serverDir
  Info 'venv built and gads_write installed'
}

# --------------------------------------------------------------------------
Step 'MCP servers'
$manifest = Get-Content (Join-Path $root 'servers\manifest.json') -Raw | ConvertFrom-Json
# Forward slashes are valid in Windows paths and keep the JSON free of escaping.
$rootFwd  = $root -replace '\\', '/'

function Resolve-Def($entry) {
  $def = $entry.windows
  $out = [ordered]@{}
  foreach ($p in $def.PSObject.Properties) {
    $v = $p.Value
    if ($v -is [string]) { $v = $v -replace '__ROOT__', $rootFwd }
    elseif ($v -is [array]) { $v = @($v | ForEach-Object { "$_" -replace '__ROOT__', $rootFwd }) }
    $out[$p.Name] = $v
  }
  [pscustomobject]$out
}

$cj = if (Test-Path $claudeJson) { Get-Content $claudeJson -Raw | ConvertFrom-Json } else { [pscustomobject]@{} }
if (Test-Path $claudeJson) { Copy-Item $claudeJson "$claudeJson.bak-$stamp" }

# user scope -> top-level mcpServers
if (-not $cj.PSObject.Properties['mcpServers']) {
  $cj | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
}
foreach ($p in $manifest.user.PSObject.Properties) {
  $def = Resolve-Def $p.Value
  if ($cj.mcpServers.PSObject.Properties[$p.Name]) { $cj.mcpServers.PSObject.Properties.Remove($p.Name) }
  $cj.mcpServers | Add-Member -NotePropertyName $p.Name -NotePropertyValue $def -Force
  Info "user scope: $($p.Name)"
}

# project scope -> projects.<abs path>.mcpServers
if (-not $cj.PSObject.Properties['projects']) {
  $cj | Add-Member -NotePropertyName projects -NotePropertyValue ([pscustomobject]@{})
}
foreach ($proj in $manifest.projects.PSObject.Properties) {
  $projPath = Join-Path $ProjectsRoot $proj.Name
  if (-not (Test-Path $projPath)) {
    Warn "project not on this machine, skipping: $projPath"
    $todo.Add("clone $($proj.Name) into $ProjectsRoot, then re-run bootstrap")
    continue
  }
  if (-not $cj.projects.PSObject.Properties[$projPath]) {
    $cj.projects | Add-Member -NotePropertyName $projPath -NotePropertyValue ([pscustomobject]@{})
  }
  $node = $cj.projects.$projPath
  if (-not $node.PSObject.Properties['mcpServers']) {
    $node | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{})
  }
  foreach ($s in $proj.Value.PSObject.Properties) {
    $node.mcpServers | Add-Member -NotePropertyName $s.Name -NotePropertyValue (Resolve-Def $s.Value) -Force
    Info "$($proj.Name): $($s.Name)"
  }
}

Save-Json $claudeJson $cj

# --------------------------------------------------------------------------
Step 'Remaining manual steps'
$todo.Add('gcloud auth application-default login --scopes https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform')
$todo.Add('pipx install git+https://github.com/googleads/google-ads-mcp.git   (speeds up serenite-ads startup)')
$todo.Add('run: claude mcp list        then authenticate box-remote-mcp with /mcp inside Claude Code')
$i = 1
foreach ($t in $todo) { Write-Host "  $i. $t"; $i++ }
Write-Host "`nDone. Backups: *.bak-$stamp`n" -ForegroundColor Green
