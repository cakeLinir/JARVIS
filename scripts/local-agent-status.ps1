param(
    [string]$LocalAgentHealthUrl = "http://127.0.0.1:8765/health",
    [int]$TimeoutSeconds = 5
)

$ErrorActionPreference = "Stop"

try {
    $response = Invoke-RestMethod -Uri $LocalAgentHealthUrl -TimeoutSec $TimeoutSeconds
    Write-Host "[OK] Lokale Agent-API erreichbar: $LocalAgentHealthUrl" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 12
    exit 0
}
catch {
    Write-Host "[ERROR] Lokale Agent-API nicht erreichbar: $LocalAgentHealthUrl" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 2
}
