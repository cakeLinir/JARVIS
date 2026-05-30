/**
 * TODO-Service-Tests — ohne echte Backend-Verbindung (In-Memory SQLite).
 * Ausführen: node --import tsx --test src/routes/todo.routes.test.ts
 */

import { test, describe, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { _setTestDb, createTestDb } from '../services/db.js';
import { createTodo, getTodoById, completeTodo, listTodos, updateTodo } from '../services/todo.service.js';
import type Database from 'better-sqlite3';

let testDb: Database.Database;

// ── Test-Setup ────────────────────────────────────────────────────────────────

before(() => {
  testDb = createTestDb();
  _setTestDb(testDb);
});

after(() => {
  _setTestDb(null);
  testDb?.close();
});

// Vor jedem Test: TODOs leeren
beforeEach(() => {
  testDb.exec("DELETE FROM todos");
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('createTodo', () => {

  test('erstellt TODO mit Pflichtfeldern und gibt id zurück', () => {
    const todo = createTodo({ title: 'Test-Aufgabe', source: 'dashboard' });

    assert.ok(todo.id, 'id muss vorhanden sein');
    assert.equal(todo.title, 'Test-Aufgabe');
    assert.equal(todo.status, 'open');
    assert.equal(todo.priority, 3);  // Standard-Priorität
    assert.ok(todo.createdAt, 'createdAt muss gesetzt sein');
    assert.ok(todo.updatedAt, 'updatedAt muss gesetzt sein');
    assert.equal(todo.completedAt, undefined);
  });

  test('setzt Standardwerte korrekt', () => {
    const todo = createTodo({ title: 'Minimal' });

    assert.equal(todo.status, 'open');
    assert.equal(todo.priority, 3);
    assert.equal(todo.source, 'manual');
    assert.deepEqual(todo.history.length, 1);  // created-Eintrag
    assert.equal(todo.history[0].action, 'created');
  });

  test('nimmt optionale Felder an', () => {
    const todo = createTodo({
      title: 'Aufgabe mit Details',
      dueDate: '2026-12-31',
      priority: 1,
      category: 'arbeit',
      source: 'voice',
    });

    assert.equal(todo.dueDate, '2026-12-31');
    assert.equal(todo.priority, 1);
    assert.equal(todo.category, 'arbeit');
    assert.equal(todo.source, 'voice');
  });

  test('speichert Recurrence-Konfiguration', () => {
    const todo = createTodo({
      title: 'Wöchentliche Aufgabe',
      dueDate: '2026-07-01',
      recurrence: { type: 'weekly', interval: 1 },
    });

    assert.ok(todo.recurrence, 'recurrence muss gesetzt sein');
    assert.equal(todo.recurrence?.type, 'weekly');
    assert.equal(todo.recurrence?.interval, 1);
  });
});

describe('getTodoById', () => {

  test('gibt vorhandenes TODO zurück', () => {
    const created = createTodo({ title: 'Abruf-Test' });
    const found = getTodoById(created.id);

    assert.ok(found, 'TODO muss gefunden werden');
    assert.equal(found?.id, created.id);
    assert.equal(found?.title, 'Abruf-Test');
  });

  test('gibt null zurück wenn nicht gefunden', () => {
    const result = getTodoById('nicht-vorhanden-xyz');
    assert.equal(result, null);
  });
});

describe('completeTodo', () => {

  test('setzt status=done und completedAt', () => {
    const todo = createTodo({ title: 'Zu erledigen' });
    const completed = completeTodo(todo.id);

    assert.ok(completed, 'Ergebnis muss vorhanden sein');
    assert.equal(completed?.status, 'done');
    assert.ok(completed?.completedAt, 'completedAt muss gesetzt sein');
  });

  test('fügt History-Eintrag hinzu', () => {
    const todo = createTodo({ title: 'Mit History' });
    const completed = completeTodo(todo.id, 'dashboard');

    const completedEntry = completed?.history.find(h => h.action === 'completed');
    assert.ok(completedEntry, 'completed-Eintrag muss in History sein');
    assert.equal(completedEntry?.actor, 'dashboard');
  });

  test('gibt null zurück für unbekannte ID', () => {
    const result = completeTodo('nicht-vorhanden');
    assert.equal(result, null);
  });
});

describe('listTodos (Filter status=open)', () => {

  test('gibt nur offene TODOs zurück bei status=open', () => {
    createTodo({ title: 'Offen 1' });
    createTodo({ title: 'Offen 2' });
    const todo3 = createTodo({ title: 'Erledigt' });
    completeTodo(todo3.id);

    const open = listTodos({ status: 'open' });
    assert.equal(open.length, 2);
    assert.ok(open.every(t => t.status === 'open'));
  });

  test('gibt alle zurück ohne Filter', () => {
    createTodo({ title: 'A' });
    createTodo({ title: 'B' });
    const all = listTodos({});
    assert.ok(all.length >= 2);
  });

  test('filtert nach Kategorie', () => {
    createTodo({ title: 'Arbeit', category: 'arbeit' });
    createTodo({ title: 'Privat', category: 'privat' });

    const arbeit = listTodos({ category: 'arbeit' });
    assert.equal(arbeit.length, 1);
    assert.equal(arbeit[0].title, 'Arbeit');
  });
});

describe('updateTodo', () => {

  test('aktualisiert Felder und updatedAt', () => {
    const todo = createTodo({ title: 'Original' });
    const updated = updateTodo(todo.id, { title: 'Geändert', priority: 1 });

    assert.ok(updated, 'Ergebnis muss vorhanden sein');
    assert.equal(updated?.title, 'Geändert');
    assert.equal(updated?.priority, 1);
    assert.notEqual(updated?.updatedAt, todo.createdAt);
  });

  test('gibt null zurück für unbekannte ID', () => {
    const result = updateTodo('nicht-vorhanden', { title: 'X' });
    assert.equal(result, null);
  });

  test('trägt Prioritätsänderung in History ein', () => {
    const todo = createTodo({ title: 'Prio-Test', priority: 3 });
    const updated = updateTodo(todo.id, { priority: 1 }, 'voice');

    const prioEntry = updated?.history.find(h => h.action === 'priority_changed');
    assert.ok(prioEntry, 'priority_changed-Eintrag muss in History sein');
    assert.equal(prioEntry?.oldValue, '3');
    assert.equal(prioEntry?.newValue, '1');
  });
});
