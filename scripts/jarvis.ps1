param(
    [Parameter(Position = 0)]
    [string]$Area,

    [Parameter(Position = 1)]
    [string]$Action,

    [string]$RepoRoot = (Resolve-Path ".").Path,

    [switch]$Build,
    [switch]$ReloadCaddy,
    [switch]$AtStartup,
    [switch]$AtLogon,
    [switch]$AllowInsecurePublicHttp,
    [int]$EveryMinutes = 5
)

$ErrorActionPreference = "Stop"

function Write-Usage {
    Write-Host "JARVIS Operations CLI" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Nutzung:"
    Write-Host "  .\scripts\jarvis.ps1 <area> <action> [options]"
    Write-Host ""
    Write-Host "Backend:"
    Write-Host "  backend start [-Build]"
    Write-Host "  backend stop"
    Write-Host "  backend restart [-Build]"
    Write-Host "  backend status"
    Write-Host "  backend health"
    Write-Host ""
    Write-Host "Backend Task:"
    Write-Host "  task install [-AtStartup|-AtLogon]"
    Write-Host "  task uninstall"
    Write-Host "  task status"
    Write-Host ""
    Write-Host "Watchdog:"
    Write-Host "  watchdog run"
    Write-Host "  watchdog install [-EveryMinutes 5]"
    Write-Host "  watchdog uninstall"
    Write-Host ""
    Write-Host "Agent:"
    Write-Host "  agent start"
    Write-Host "  agent stop"
    Write-Host "  agent status"
    Write-Host "  agent diagnose"
    Write-Host "  agent config"
    Write-Host "  agent install-task"
    Write-Host "  agent uninstall-task"
    Write-Host ""
    Write-Host "Dashboard:"
    Write-Host "  dashboard check"
    Write-Host "  dashboard build"
    Write-Host "  dashboard deploy [-ReloadCaddy]"
    Write-Host ""
    Write-Host "Caddy:"
    Write-Host "  caddy install [-ReloadCaddy]"
    Write-Host "  caddy health"
    Write-Host ""
    Write-Host "Config:"
    Write-Host "  config https"
    Write-Host "  config public -AllowInsecurePublicHttp"
    Write-Host ""
    Write-Host "Preflight:"
    Write-Host "  preflight local"
    Write-Host "  preflight vps"
    Write-Host ""
}

function Invoke-JarvisScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [hashtable]$NamedArgs = @{}
    )

    $scriptPath = Join-Path $RepoRoot $RelativePath

    if (-not (Test-Path $scriptPath)) {
        Write-Host "[ERROR] Skript nicht gefunden: $RelativePath" -ForegroundColor Red
        exit 2
    }

    & $scriptPath @NamedArgs
    exit $LASTEXITCODE
}

if (-not $Area -or -not $Action -or $Area -in @("help", "-h", "--help", "/?")) {
    Write-Usage
    exit 0
}

$areaKey = $Area.Trim().ToLowerInvariant()
$actionKey = $Action.Trim().ToLowerInvariant()

switch ($areaKey) {
    "backend" {
        switch ($actionKey) {
            "start" {
                $args = @{ RepoRoot = $RepoRoot }
                if ($Build) { $args["Build"] = $true }
                Invoke-JarvisScript "scripts\backend-start.ps1" -NamedArgs $args
            }
            "stop" {
                Invoke-JarvisScript "scripts\backend-stop.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "restart" {
                $args = @{ RepoRoot = $RepoRoot }
                if ($Build) { $args["Build"] = $true }
                Invoke-JarvisScript "scripts\backend-restart.ps1" -NamedArgs $args
            }
            "status" {
                Invoke-JarvisScript "scripts\backend-status.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "health" {
                Invoke-JarvisScript "scripts\backend-health.ps1"
            }
            default { Write-Usage; exit 2 }
        }
    }

    "task" {
        switch ($actionKey) {
            "install" {
                $args = @{ RepoRoot = $RepoRoot }
                if ($AtStartup) { $args["AtStartup"] = $true }
                if ($AtLogon) { $args["AtLogon"] = $true }
                Invoke-JarvisScript "scripts\install-backend-task.ps1" -NamedArgs $args
            }
            "uninstall" {
                Invoke-JarvisScript "scripts\uninstall-backend-task.ps1"
            }
            "status" {
                Invoke-JarvisScript "scripts\backend-task-status.ps1"
            }
            default { Write-Usage; exit 2 }
        }
    }

    "watchdog" {
        switch ($actionKey) {
            "run" {
                Invoke-JarvisScript "scripts\backend-watchdog.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "install" {
                Invoke-JarvisScript "scripts\install-backend-watchdog-task.ps1" -NamedArgs @{
                    RepoRoot = $RepoRoot
                    EveryMinutes = $EveryMinutes
                }
            }
            "uninstall" {
                Invoke-JarvisScript "scripts\uninstall-backend-watchdog-task.ps1"
            }
            default { Write-Usage; exit 2 }
        }
    }

    "agent" {
        switch ($actionKey) {
            "start" {
                Invoke-JarvisScript "scripts\run-local-agent.cmd"
            }
            "stop" {
                Invoke-JarvisScript "scripts\stop-local-agent.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "status" {
                Invoke-JarvisScript "scripts\local-agent-status.ps1"
            }
            "diagnose" {
                Invoke-JarvisScript "scripts\diagnose-local-agent-vps.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "config" {
                Invoke-JarvisScript "scripts\configure-local-agent-vps.ps1" -NamedArgs @{
                    RepoRoot = $RepoRoot
                    BackendUrl = "https://jarvis.hundekuchenlive.de"
                    AgentName = "jarvis-desktop-agent"
                }
            }
            "install-task" {
                Invoke-JarvisScript "scripts\install-local-agent-task.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "uninstall-task" {
                Invoke-JarvisScript "scripts\uninstall-local-agent-task.ps1"
            }
            default { Write-Usage; exit 2 }
        }
    }

    "dashboard" {
        switch ($actionKey) {
            "check" {
                Invoke-JarvisScript "scripts\vps-dashboard-source-check.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "build" {
                Invoke-JarvisScript "scripts\dashboard-build.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "deploy" {
                $args = @{ RepoRoot = $RepoRoot }
                if ($ReloadCaddy) { $args["ReloadCaddy"] = $true }
                Invoke-JarvisScript "scripts\deploy-dashboard.ps1" -NamedArgs $args
            }
            default { Write-Usage; exit 2 }
        }
    }

    "caddy" {
        switch ($actionKey) {
            "install" {
                $args = @{ RepoRoot = $RepoRoot }
                if ($ReloadCaddy) { $args["Reload"] = $true }
                Invoke-JarvisScript "scripts\caddy-install-jarvis-config.ps1" -NamedArgs $args
            }
            "health" {
                Invoke-JarvisScript "scripts\caddy-health.ps1"
            }
            default { Write-Usage; exit 2 }
        }
    }

    "config" {
        switch ($actionKey) {
            "https" {
                Invoke-JarvisScript "scripts\configure-https-backend.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "public" {
                if (-not $AllowInsecurePublicHttp) {
                    Write-Host "[ERROR] SICHERHEITSRISIKO: Direkte Public-HTTP-Konfiguration ist blockiert." -ForegroundColor Red
                    Write-Host "Nutze bewusst: .\scripts\jarvis.ps1 config public -AllowInsecurePublicHttp"
                    exit 2
                }

                Invoke-JarvisScript "scripts\configure-public-backend.ps1" -NamedArgs @{
                    RepoRoot = $RepoRoot
                    AllowInsecurePublicHttp = $true
                }
            }
            default { Write-Usage; exit 2 }
        }
    }

    "preflight" {
        switch ($actionKey) {
            "local" {
                Invoke-JarvisScript "scripts\preflight-local.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            "vps" {
                Invoke-JarvisScript "scripts\preflight-vps.ps1" -NamedArgs @{ RepoRoot = $RepoRoot }
            }
            default { Write-Usage; exit 2 }
        }
    }

    default {
        Write-Usage
        exit 2
    }
}
