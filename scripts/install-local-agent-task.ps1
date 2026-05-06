param(
    [Parameter(Mandatory = $true)]
    [string]$JarvisRoot,

    [string]$TaskName = "JARVIS Local Agent",
    [string]$PythonCommand = "py"
)

$agentScript = Join-Path $JarvisRoot "desktop-agent\src\main.py"

if (-not (Test-Path $agentScript)) {
    throw "Agent-Script nicht gefunden: $agentScript"
}

$action = New-ScheduledTaskAction `
    -Execute $PythonCommand `
    -Argument "-3 `"$agentScript`"" `
    -WorkingDirectory (Join-Path $JarvisRoot "desktop-agent")

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Startet den lokalen JARVIS Desktop-Agent nach Windows-Login." `
    -Force

Write-Host "Scheduled Task installiert: $TaskName"
