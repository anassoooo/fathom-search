<#
.SYNOPSIS
  Register (or replace) the "VIO daily eval" scheduled task for the current user.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\register_daily_eval.ps1            # daily at 18:00
  powershell -ExecutionPolicy Bypass -File scripts\register_daily_eval.ps1 -At 20:30
  Unregister-ScheduledTask -TaskName "VIO daily eval" -Confirm:$false                 # remove it
#>
param([string]$At = "18:00")

$script = Join-Path $PSScriptRoot "daily_eval.ps1"
$ps = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$action = New-ScheduledTaskAction -Execute $ps `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# Run late if the laptop was off/asleep at the scheduled time; give it up to 3 hours.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3)
# Runs as you, only while you're logged on (Docker Desktop is a per-user app).
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName "VIO daily eval" -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description "Judge ~50 more eval queries within Groq's free daily quota and refresh the report (VIO)." `
    -Force | Out-Null
Get-ScheduledTask -TaskName "VIO daily eval" | Get-ScheduledTaskInfo |
    Select-Object TaskName, NextRunTime
