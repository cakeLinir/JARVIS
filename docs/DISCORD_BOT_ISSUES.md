# JARVIS Discord-Bot — Geplante Commands

Dieses Dokument beschreibt die geplanten Slash-Commands für den Discord-Bot
im Repo `cakeLinir/discord_bot_hundekuchenlive`.

Jeder Abschnitt entspricht einem GitHub-Issue der dort erstellt werden soll.

---

## Issue 1: `/todo add` — TODO per Discord anlegen

**Titel:** `feat: /todo add <titel> [--datum] [--priorität]`

**Beschreibung:**

Neuen Task über Discord erstellen. Wird an das JARVIS-Backend weitergeleitet.

**Command-Syntax:**
```
/todo add <titel> [--datum YYYY-MM-DD] [--priorität hoch|mittel|niedrig]
```

**Beispiele:**
```
/todo add Rechnung bezahlen
/todo add Arzttermin --datum 2026-06-15 --priorität hoch
```

**Backend-Endpunkt:**
```http
POST /api/todos
Authorization: Bearer <JARVIS_BOT_BRIDGE_TOKEN>
Content-Type: application/json

{
  "title": "Rechnung bezahlen",
  "dueDate": "2026-06-15",
  "priority": 2,
  "source": "discord"
}
```

**Bot-Response:**
```
✅ Aufgabe angelegt: **Rechnung bezahlen**
📅 Fällig: 15.06.2026 | 🔴 Priorität: Hoch
```

**Prioritäts-Mapping:**

| Discord | API (int) |
|---|---|
| kritisch | 1 |
| hoch | 2 |
| mittel | 3 |
| niedrig | 4 |
| optional | 5 |

**Fehlerbehandlung:**
- Fehlender Titel → „Bitte einen Titel angeben."
- Backend nicht erreichbar → „JARVIS antwortet gerade nicht. Bitte später erneut versuchen."

---

## Issue 2: `/todo list` — Offene TODOs anzeigen

**Titel:** `feat: /todo list [--heute]`

**Beschreibung:**

Listet offene Tasks auf. `--heute` zeigt nur heute fällige.

**Command-Syntax:**
```
/todo list
/todo list --heute
```

**Backend-Endpunkte:**
```http
# Alle offenen
GET /api/todos?status=open&limit=10
Authorization: Bearer <JARVIS_BOT_BRIDGE_TOKEN>

# Nur heute fällig
GET /api/todos/today
Authorization: Bearer <JARVIS_BOT_BRIDGE_TOKEN>
```

**Bot-Response (Beispiel):**
```
📋 **Offene Aufgaben (3)**

🔴 Kritisch:
  • Serverausfall beheben

🟠 Hoch:
  • Rechnung bezahlen — fällig: 15.06.2026

⚪ Mittel:
  • Einkauf erledigen
```

**Formatierungsregeln:**
- Priorität 1 → 🔴 Kritisch
- Priorität 2 → 🟠 Hoch
- Priorität 3 → 🟡 Mittel
- Priorität 4 → 🟢 Niedrig
- Priorität 5 → ⚪ Optional
- Max. 10 Einträge pro Nachricht (paginiert bei Bedarf)

---

## Issue 3: `/shift set` — Schicht eintragen

**Titel:** `feat: /shift set <datum> <typ>`

**Beschreibung:**

Schicht für ein Datum eintragen. Verhindert Doppeleintrag (HTTP 409).

**Command-Syntax:**
```
/shift set <datum> <typ>
```

**Typ-Optionen:** `tag` | `nacht` | `frueh` | `spaet` | `frei`

**Mapping Discord → API:**
| Discord | API `type` |
|---|---|
| tag | tag |
| nacht | nacht |
| frueh | fakt_frueh |
| spaet | fakt_spaet |
| frei | frei |

**Beispiele:**
```
/shift set 2026-06-15 tag
/shift set 2026-06-16 nacht
/shift set 2026-06-17 frei
```

**Backend-Endpunkt:**
```http
POST /api/shifts
Authorization: Bearer <JARVIS_BOT_BRIDGE_TOKEN>
Content-Type: application/json

{
  "date": "2026-06-15",
  "type": "tag",
  "source": "discord"
}
```

**Bot-Response:**
```
✅ Schicht eingetragen für **15.06.2026**:
🏭 Tagschicht — 07:00 bis 19:00 Uhr
```

**Fehlerbehandlung:**
- HTTP 409 → „Für dieses Datum ist bereits eine Schicht eingetragen. `/shift update` zum Ändern."
- Ungültiger Typ → Dropdown-Auswahl anzeigen

---

## Issue 4: `/stream` — Streaming-Empfehlung abrufen

**Titel:** `feat: /stream [datum]`

**Beschreibung:**

Zeigt ob und wann Streaming sinnvoll ist, basierend auf der eingetragenen Schicht.

**Command-Syntax:**
```
/stream
/stream 2026-06-15
```

**Backend-Endpunkt:**
```http
GET /api/availability/2026-06-15?current_hour=14
Authorization: Bearer <JARVIS_BOT_BRIDGE_TOKEN>
```

**Empfehlungs-Mapping:**

| `streamRecommendation` | Emoji | Text |
|---|---|---|
| free | 🟢 | Jederzeit möglich |
| conditional | 🟡 | Bedingt möglich |
| discouraged | 🟠 | Nicht empfohlen |
| blocked | 🔴 | Kein Stream |

**Bot-Response (Beispiel):**
```
📅 **Streaming-Empfehlung für 15.06.2026**

🟡 **Bedingt möglich**
⏰ Fenster: 19:30 – 22:00 Uhr
🏭 Schicht: Tagschicht (07:00 – 19:00)

ℹ️ Nach der Tagschicht — kurzer entspannter Stream bis 22 Uhr.
```

**Kein Schicht-Eintrag:**
```
📅 **Streaming-Empfehlung für 15.06.2026**

🟡 Keine Schicht eingetragen.
Trage deine Schicht ein: `/shift set 2026-06-15 <typ>`
```

---

## Authentifizierung

Alle Bot-Requests verwenden den `JARVIS_BOT_BRIDGE_TOKEN` als Bearer-Token.
Dieser Token muss in der Bot-Umgebung als `JARVIS_BOT_BRIDGE_TOKEN` gesetzt sein
und im Backend in der `.env`-Datei als `JARVIS_BOT_BRIDGE_TOKEN` eingetragen werden.

Die Middleware `requireBotAuth` oder `requireAnyJarvisAuth` schützt die Endpunkte.
