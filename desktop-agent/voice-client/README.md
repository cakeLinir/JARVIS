# JARVIS Voice Client Scaffold

Dieser Ordner ist der Startpunkt für den späteren Electron/Tauri/Browser-basierten Voice-Client.

Der produktive Voice-Client soll:

1. lokal Wake-Word erkennen,
2. vom VPS ein OpenAI Realtime Client Secret holen,
3. per WebRTC Audio senden/empfangen,
4. Tool-Calls auf die lokale Python-Agent-API routen.

Der OpenAI-Key bleibt ausschließlich im Backend.
