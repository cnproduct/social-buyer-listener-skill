param(
  [string]$Message = "Update social buyer listener skill"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Validator = "C:\Users\Administrator\.codex\skills\.system\skill-creator\scripts\quick_validate.py"

Set-Location $RepoRoot

if (Test-Path $Validator) {
  python $Validator $RepoRoot
}

$changes = git status --porcelain
if (-not $changes) {
  Write-Host "No changes to publish."
  exit 0
}

git add .
git commit -m $Message
git push
