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

function Invoke-Script {
    param(
        [string]$RelativePath,
        [string[]]$Arguments = @()
    )

    $scriptPath = Join-Path $RepoRoot $RelativePath

    if (-not (Test-Path $scriptPath)) {
        Write-Host "[ERROR] Skript nicht gefunden: $RelativePath" -ForegroundColor Red
        exit 2
    }

    & $scriptPath @Arguments
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
                $args = @("-RepoRoot", $RepoRoot)
                if ($Build) { $args += "-Build" }
                Invoke-Script "scripts\backend-start.ps1" $args
            }
            "stop" {
                Invoke-Script "scripts\backend-stop.ps1" @("-RepoRoot", $RepoRoot)
            }
            "restart" {
                $args = @("-RepoRoot", $RepoRoot)
                if ($Build) { $args += "-Build" }
                Invoke-Script "scripts\backend-restart.ps1" $args
            }
            "status" {
                Invoke-Script "scripts\backend-status.ps1" @("-RepoRoot", $RepoRoot)
            }
            "health" {
                Invoke-Script "scripts\backend-health.ps1"
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    "task" {
        switch ($actionKey) {
            "install" {
                $args = @("-RepoRoot", $RepoRoot)
                if ($AtStartup) { $args += "-AtStartup" }
                if ($AtLogon) { $args += "-AtLogon" }
                Invoke-Script "scripts\install-backend-task.ps1" $args
            }
            "uninstall" {
                Invoke-Script "scripts\uninstall-backend-task.ps1"
            }
            "status" {
                Invoke-Script "scripts\backend-task-status.ps1"
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    "watchdog" {
        switch ($actionKey) {
            "run" {
                Invoke-Script "scripts\backend-watchdog.ps1" @("-RepoRoot", $RepoRoot)
            }
            "install" {
                Invoke-Script "scripts\install-backend-watchdog-task.ps1" @("-RepoRoot", $RepoRoot, "-EveryMinutes", "$EveryMinutes")
            }
            "uninstall" {
                Invoke-Script "scripts\uninstall-backend-watchdog-task.ps1"
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    "dashboard" {
        switch ($actionKey) {
            "check" {
                Invoke-Script "scripts\vps-dashboard-source-check.ps1" @("-RepoRoot", $RepoRoot)
            }
            "build" {
                Invoke-Script "scripts\dashboard-build.ps1" @("-RepoRoot", $RepoRoot)
            }
            "deploy" {
                $args = @("-RepoRoot", $RepoRoot)
                if ($ReloadCaddy) { $args += "-ReloadCaddy" }
                Invoke-Script "scripts\deploy-dashboard.ps1" $args
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    "caddy" {
        switch ($actionKey) {
            "install" {
                $args = @("-RepoRoot", $RepoRoot)
                if ($ReloadCaddy) { $args += "-Reload" }
                Invoke-Script "scripts\caddy-install-jarvis-config.ps1" $args
            }
            "health" {
                Invoke-Script "scripts\caddy-health.ps1"
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    "config" {
        switch ($actionKey) {
            "https" {
                Invoke-Script "scripts\configure-https-backend.ps1" @("-RepoRoot", $RepoRoot)
            }
            "public" {
                if (-not $AllowInsecurePublicHttp) {
                    Write-Host "[ERROR] SICHERHEITSRISIKO: Direkte Public-HTTP-Konfiguration ist blockiert." -ForegroundColor Red
                    Write-Host "Nutze bewusst: .\scripts\jarvis.ps1 config public -AllowInsecurePublicHttp"
                    exit 2
                }

                Invoke-Script "scripts\configure-public-backend.ps1" @("-RepoRoot", $RepoRoot)
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    "preflight" {
        switch ($actionKey) {
            "local" {
                Invoke-Script "scripts\preflight-local.ps1" @("-RepoRoot", $RepoRoot)
            }
            "vps" {
                Invoke-Script "scripts\preflight-vps.ps1" @("-RepoRoot", $RepoRoot)
            }
            default {
                Write-Usage
                exit 2
            }
        }
    }

    default {
        Write-Usage
        exit 2
    }
}
