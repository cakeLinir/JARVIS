# JARVIS VPS Ordnerstrategie

## Patch 022.1 Hinweis

`git sparse-checkout init --cone` akzeptiert bei `git sparse-checkout set` nur Verzeichnisse.

Deshalb werden nur diese Ordner gesetzt:

```text
backend
dashboard
deploy
docs
scripts
```

Root-Dateien wie diese werden im Cone-Mode normalerweise automatisch mitgeführt:

```text
.gitignore
README.md
LICENSE
```

Der frühere Fehler:

```text
fatal: '.gitignore' is not a directory
```

kam daher, dass `.gitignore` eine Datei ist und fälschlich an `git sparse-checkout set` übergeben wurde.

## Ziel

Der VPS soll nicht nur `backend/` ziehen. Seit der Frontend/Backend-Trennung braucht der VPS produktiv:

```text
backend/
dashboard/
deploy/
docs/
scripts/
.gitignore
README.md
LICENSE
```

Nicht nötig auf dem VPS:

```text
desktop-agent/
.venv/
.jarvis-patch-backups/
logs/
```

## Warum `dashboard/` nötig ist

Caddy serviert ab Patch 019:

```text
dashboard/dist
```

Dieser Ordner entsteht durch:

```powershell
.\scripts\dashboard-build.ps1
```

Dafür muss vorhanden sein:

```text
dashboard/package.json
```

## Sparse Checkout konfigurieren

Auf dem VPS:

```powershell
cd C:\Bots\JARVIS
.\scripts\configure-vps-sparse-checkout.ps1 -ApplyPull
```

Danach prüfen:

```powershell
Test-Path .\dashboard\package.json
Test-Path .\deploy\caddy\Caddyfile
```

Beide sollten `True` sein.

## VPS Update

Nach lokalem Commit/Push:

```powershell
cd C:\Bots\JARVIS
.\scripts\vps-update-project.ps1
```

Das führt aus:

- `git pull`
- Backend Dependencies/Build
- Dashboard Dependencies/Build
- Caddy Reload

## Minimaler Ablauf

```powershell
cd C:\Bots\JARVIS
.\scripts\configure-vps-sparse-checkout.ps1 -ApplyPull
.\scripts\configure-https-backend.ps1
.\scripts\vps-update-project.ps1
.\scripts\caddy-health.ps1
```

## Sicherheitsregel

`configure-public-backend.ps1` nicht verwenden, außer bewusst für Testbetrieb mit:

```powershell
-AllowInsecurePublicHttp
```

Produktiv ist:

```powershell
.\scripts\configure-https-backend.ps1
```
