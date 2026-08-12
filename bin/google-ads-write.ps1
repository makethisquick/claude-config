# Windows launcher for the Google Ads WRITE MCP server (servers/google-ads-write).
#
# WARNING: this server can change live advertising accounts. Every mutating tool
# defaults to a dry run (validate_only) and requires confirm=true to write.
#
# Windows port of google-ads-write.sh. The venv is NOT synced between machines —
# bootstrap.ps1 creates it locally from the synced source in servers/google-ads-write.
#
# Usage (from servers/manifest.json):
#   powershell -NoProfile -ExecutionPolicy Bypass -File google-ads-write.ps1 <gcp-project-id> [login-customer-id]

param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$LoginCustomerId
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Die($msg) { [Console]::Error.WriteLine($msg); exit 1 }

$serverDir = Join-Path $root 'servers\google-ads-write'
$python    = Join-Path $serverDir '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
  Die @"
Server venv missing at $python
Rebuild with:
  py -3 -m venv "$serverDir\.venv"
  & "$python" -m pip install -e "$serverDir"
"@
}

$devToken = $env:GOOGLE_ADS_DEVELOPER_TOKEN
if (-not $devToken) {
  $credPath = Join-Path $root 'secrets\credentials.json'
  if (Test-Path $credPath) {
    $devToken = (Get-Content $credPath -Raw | ConvertFrom-Json).googleAds.GOOGLE_ADS_DEVELOPER_TOKEN
  }
}
if (-not $devToken) {
  Die "No Google Ads developer token. See the message from google-ads-mcp.ps1 for how to set one."
}

$adc = $env:GOOGLE_APPLICATION_CREDENTIALS
if (-not $adc) { $adc = Join-Path $env:APPDATA 'gcloud\application_default_credentials.json' }
if (-not (Test-Path $adc)) {
  Die @"
No Application Default Credentials at: $adc
Create them with:
  gcloud auth application-default login --scopes https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform
"@
}

$env:GOOGLE_ADS_DEVELOPER_TOKEN     = $devToken
$env:GOOGLE_APPLICATION_CREDENTIALS = $adc
$env:GOOGLE_PROJECT_ID              = $ProjectId
$env:GOOGLE_CLOUD_PROJECT           = $ProjectId

if ($LoginCustomerId) { $env:GOOGLE_ADS_LOGIN_CUSTOMER_ID = $LoginCustomerId -replace '-', '' }

& $python -m gads_write.server
exit $LASTEXITCODE
