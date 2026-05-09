param(
    [string]$Url = "http://127.0.0.1:8181/api/health",
    [int]$TimeoutSeconds = 5,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

try {
    $response = Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSeconds

    if ($response.status -eq "ok" -or $response.ok -eq $true) {
        if (-not $Quiet) {
            Write-Host "[OK] Backend Health OK: $Url" -ForegroundColor Green
            $response | ConvertTo-Json -Depth 8
        }
        exit 0
    }

    if (-not $Quiet) {
        Write-Host "[WARN] Backend Health antwortet, aber Status ist nicht ok: $Url" -ForegroundColor Yellow
        $response | ConvertTo-Json -Depth 8
    }
    exit 1
}
catch {
    if (-not $Quiet) {
        Write-Host "[ERROR] Backend Health nicht erreichbar: $Url | $($_.Exception.Message)" -ForegroundColor Red
    }
    exit 2
}
