# Windows launcher for the official Google Ads MCP server (googleads/google-ads-mcp).
#
# Windows port of google-ads-mcp.sh. The Mac version pulls the developer token from
# the Keychain; there is no drop-in equivalent here, so the token comes from either
# the GOOGLE_ADS_DEVELOPER_TOKEN environment variable or ..\secrets\credentials.json.
#
# Everything written to stdout is part of the MCP stdio stream, so all diagnostics
# go to stderr via [Console]::Error.
#
# Usage (from servers/manifest.json):
#   powershell -NoProfile -ExecutionPolicy Bypass -File google-ads-mcp.ps1 <gcp-project-id> [login-customer-id]

param(
  [Parameter(Mandatory = $true)][string]$ProjectId,
  [string]$LoginCustomerId
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Die($msg) { [Console]::Error.WriteLine($msg); exit 1 }

# --- developer token -------------------------------------------------------
$devToken = $env:GOOGLE_ADS_DEVELOPER_TOKEN
if (-not $devToken) {
  $credPath = Join-Path $root 'secrets\credentials.json'
  if (Test-Path $credPath) {
    $devToken = (Get-Content $credPath -Raw | ConvertFrom-Json).googleAds.GOOGLE_ADS_DEVELOPER_TOKEN
  }
}
if (-not $devToken) {
  Die @"
No Google Ads developer token.
Set it once for your user account:
  setx GOOGLE_ADS_DEVELOPER_TOKEN "<developer-token>"
(then open a new terminal), or fill googleAds.GOOGLE_ADS_DEVELOPER_TOKEN in
  $root\secrets\credentials.json
The token is in Google Ads > Tools > Setup > API Center on the manager (MCC) account.
"@
}

# --- Application Default Credentials ---------------------------------------
$adc = $env:GOOGLE_APPLICATION_CREDENTIALS
if (-not $adc) { $adc = Join-Path $env:APPDATA 'gcloud\application_default_credentials.json' }
if (-not (Test-Path $adc)) {
  Die @"
No Application Default Credentials at: $adc
Create them with:
  gcloud auth application-default login --scopes https://www.googleapis.com/auth/adwords,https://www.googleapis.com/auth/cloud-platform
"@
}

$env:GOOGLE_ADS_DEVELOPER_TOKEN   = $devToken
$env:GOOGLE_APPLICATION_CREDENTIALS = $adc
$env:GOOGLE_PROJECT_ID            = $ProjectId
$env:GOOGLE_CLOUD_PROJECT         = $ProjectId

# Google Ads shows customer IDs as 123-456-7890; the API wants them bare.
if ($LoginCustomerId) { $env:GOOGLE_ADS_LOGIN_CUSTOMER_ID = $LoginCustomerId -replace '-', '' }

# Prefer the pipx-installed entry point (fast start). Fall back to pipx run, which
# builds from git on first use and can be slow enough to trip the client's startup timeout.
$exe = Join-Path $env:USERPROFILE '.local\bin\google-ads-mcp.exe'
if (Test-Path $exe) {
  & $exe
  exit $LASTEXITCODE
}

& pipx run --spec git+https://github.com/googleads/google-ads-mcp.git google-ads-mcp
exit $LASTEXITCODE
