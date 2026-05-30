import Database from 'better-sqlite3';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// DB-Pfad: backend/.runtime/data/jarvis.db
const DB_PATH = path.resolve(__dirname, '../../.runtime/data/jarvis.db');

let _db: Database.Database | null = null;

// ── Test-Hilfsfunktion ────────────────────────────────────────────────────────

/**
 * Injiziert eine externe DB-Instanz (z.B. In-Memory für Tests).
 * Nur in Testumgebungen verwenden.
 */
export function _setTestDb(db: Database.Database | null): void {
  _db = db;
}

/** Erstellt eine In-Memory-DB mit vollständigen Migrationen — für Unit-Tests. */
export function createTestDb(): Database.Database {
  const db = new Database(':memory:');
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  runMigrations(db);
  return db;
}

// ── Singleton-Getter ──────────────────────────────────────────────────────────

/** Gibt initialisierte SQLite-DB-Instanz zurück. Singleton pro Prozess. */
export function getDb(): Database.Database {
  if (_db) return _db;

  fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

  _db = new Database(DB_PATH);
  _db.pragma('journal_mode = WAL');
  _db.pragma('foreign_keys = ON');

  runMigrations(_db);

  return _db;
}

// ── Versioned Migrations ──────────────────────────────────────────────────────

type Migration = {
  version: number;
  name: string;
  sql: string;
};

/**
 * Alle Datenbank-Migrationen in aufsteigender Reihenfolge.
 * Jede Migration wird genau einmal ausgeführt — SQL muss idempotent sein
 * (CREATE TABLE IF NOT EXISTS, INSERT OR IGNORE, CREATE UNIQUE INDEX IF NOT EXISTS).
 */
const MIGRATIONS: Migration[] = [
  {
    version: 1,
    name: 'create_todos',
    sql: `
      CREATE TABLE IF NOT EXISTS todos (
        id           TEXT    PRIMARY KEY,
        title        TEXT    NOT NULL,
        description  TEXT    NOT NULL DEFAULT '',
        status       TEXT    NOT NULL DEFAULT 'open',
        priority     INTEGER NOT NULL DEFAULT 3,
        category     TEXT    NOT NULL DEFAULT '',
        due_date     TEXT    DEFAULT NULL,
        due_time     TEXT    DEFAULT NULL,
        start_date   TEXT    DEFAULT NULL,
        recurrence   TEXT    NOT NULL DEFAULT 'none',
        reminder_min INTEGER DEFAULT NULL,
        shift_id     TEXT    DEFAULT NULL,
        source       TEXT    NOT NULL DEFAULT 'manual',
        created_at   TEXT    NOT NULL,
        updated_at   TEXT    NOT NULL,
        completed_at TEXT    DEFAULT NULL,
        history      TEXT    NOT NULL DEFAULT '[]'
      );
    `,
  },
  {
    version: 2,
    name: 'create_shift_types',
    sql: `
      CREATE TABLE IF NOT EXISTS shift_types (
        type                  TEXT PRIMARY KEY,
        label                 TEXT NOT NULL,
        default_start         TEXT,
        default_end           TEXT,
        crosses_midnight      INTEGER NOT NULL DEFAULT 0,
        rest_hours_before     INTEGER NOT NULL DEFAULT 8,
        rest_hours_after      INTEGER NOT NULL DEFAULT 8,
        stream_recommendation TEXT NOT NULL DEFAULT 'conditional',
        stream_reason         TEXT NOT NULL DEFAULT ''
      );

      INSERT OR IGNORE INTO shift_types VALUES
        ('tag',        'Tagschicht',     '07:00', '19:00', 0, 8, 8, 'conditional',  'Schicht endet 19:00 – Stream danach möglich.'),
        ('nacht',      'Nachtschicht',   '19:00', '07:00', 1, 8, 8, 'discouraged',  'Nachtschicht – Erholung danach erforderlich.'),
        ('fakt_frueh', 'FAKT IST! Früh', '07:00', '14:30', 0, 8, 8, 'conditional',  'Schicht endet 14:30 – Nachmittag/Abend möglich.'),
        ('fakt_spaet', 'FAKT IST! Spät', '14:30', '21:30', 0, 8, 8, 'discouraged',  'Schicht endet 21:30 – wenig Zeit danach.'),
        ('frei',       'Frei',           NULL,    NULL,    0, 0, 0, 'free',          'Freier Tag – keine Einschränkungen.');
    `,
  },
  {
    version: 3,
    name: 'create_shifts',
    sql: `
      CREATE TABLE IF NOT EXISTS shifts (
        id               TEXT    PRIMARY KEY,
        date             TEXT    NOT NULL,
        type             TEXT    NOT NULL REFERENCES shift_types(type),
        start_time       TEXT,
        end_time         TEXT,
        crosses_midnight INTEGER NOT NULL DEFAULT 0,
        end_date         TEXT,
        notes            TEXT    NOT NULL DEFAULT '',
        source           TEXT    NOT NULL DEFAULT 'manual',
        created_at       TEXT    NOT NULL,
        updated_at       TEXT    NOT NULL
      );

      CREATE UNIQUE INDEX IF NOT EXISTS idx_shifts_date ON shifts(date);
    `,
  },
];

/**
 * Führt alle ausstehenden Migrationen idempotent aus.
 * Versionstabelle wird beim ersten Aufruf angelegt.
 * Vorhandene Tabellen (IF NOT EXISTS) werden nicht erneut erstellt.
 */
export function runMigrations(db: Database.Database): void {
  // Migrations-Protokolltabelle sicherstellen
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      version    INTEGER PRIMARY KEY,
      name       TEXT    NOT NULL,
      applied_at TEXT    NOT NULL DEFAULT (datetime('now'))
    );
  `);

  // Höchste angewendete Version ermitteln
  const row = db
    .prepare('SELECT COALESCE(MAX(version), 0) AS v FROM schema_migrations')
    .get() as { v: number };
  const currentVersion = row.v;

  // Nur fehlende Migrationen ausführen
  const pending = MIGRATIONS.filter((m) => m.version > currentVersion);

  for (const migration of pending) {
    db.exec(migration.sql);
    db
      .prepare('INSERT INTO schema_migrations (version, name) VALUES (?, ?)')
      .run(migration.version, migration.name);
  }
}
