# JARVIS Architektur

## Komponenten

1. Local Client
   - läuft auf deinem Windows-PC
   - startet Programme
   - steuert Fenster
   - verarbeitet Wake-Words
   - spricht mit Backend

2. Windows-VPS Backend
   - API
   - WebSocket
   - OpenAI-Service
   - News-Service
   - Authentifizierung
   - Logging

3. Nextcord Bot Bridge
   - verbindet vorhandenen VPS-Bot mit JARVIS
   - keine Selfbot-Automation
   - keine User-Token
