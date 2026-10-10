<#
.SYNOPSIS
  Daily evaluation step under Groq's free-tier quota (~50 judged queries/day).

.DESCRIPTION
  1. Ensures Qdrant is running (docker compose).
  2. Runs `vio eval judge`: keeps every existing judgment, sends the judge only
     unjudged (query, product) pairs until the daily token quota is used.
  3. If new queries were judged, runs `vio eval retrieval` to refresh the report.
  4. Once every query is judged, disables its own scheduled task.

  Never commits or pushes: review and commit the results yourself.
  Logs: data/eval/logs/daily_<date>.log

.NOTES
  Registered by scripts/register_daily_eval.ps1 as the task "VIO daily eval".
#>
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo "backend"
$logDir = Join-Path $repo "data\eval\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("daily_{0}.log" -f (Get-Date -Format "yyyy-MM-dd_HHmm"))
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

function Write-Log([string]$msg) {
    "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $msg | Tee-Object -FilePath $log -Append
}

function Get-JudgedCount {
    $qrels = Join-Path $repo "data\eval\qrels_v1.jsonl"
    if (-not (Test-Path $qrels)) { return 0 }
    $ids = @{}
    foreach ($line in Get-Content $qrels) { $ids[($line | ConvertFrom-Json).qid] = $true }
    return $ids.Count
}

$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv) { Write-Log "uv not found on PATH; aborting"; exit 1 }

Write-Log "Starting daily eval in $repo"
Push-Location $repo
docker compose up -d --wait qdrant *>> $log
if ($LASTEXITCODE -ne 0) { Write-Log "Qdrant did not start (is Docker Desktop running?); aborting"; Pop-Location; exit 1 }
Pop-Location

$before = Get-JudgedCount
Push-Location $backend
& $uv run --no-sync vio eval judge *>> $log
$judgeExit = $LASTEXITCODE
$after = Get-JudgedCount
Write-Log "Judge exit code $judgeExit; judged queries $before -> $after"

if ($after -gt $before) {
    & $uv run --no-sync vio eval retrieval *>> $log
    Write-Log "Retrieval report refreshed (exit $LASTEXITCODE)"
} else {
    Write-Log "No new judgments (quota not reset yet?); report unchanged"
}
Pop-Location

if ($judgeExit -eq 0) {
    Write-Log "All queries judged; disabling the scheduled task"
    Disable-ScheduledTask -TaskName "VIO daily eval" -ErrorAction SilentlyContinue | Out-Null
}
Write-Log "Done"
exit 0  # a quota-limited partial run is the normal case, not a failure
