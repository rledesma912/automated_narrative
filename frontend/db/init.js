const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

// Crear directorio db si no existe
const dbDir = path.join(__dirname, '..');
const dbPath = path.join(dbDir, 'stories.db');

let db = null;

function getDB() {
  if (!db) {
    db = new sqlite3.Database(dbPath, (err) => {
      if (err) {
        console.error('Error opening database:', err);
      } else {
        console.log('✓ Connected to SQLite database at:', dbPath);
      }
    });
    // Habilitar foreign keys
    db.run('PRAGMA foreign_keys = ON');
  }
  return db;
}

function initializeDB() {
  const database = getDB();

  database.serialize(() => {
    // Tabla de historias
    database.run(`
      CREATE TABLE IF NOT EXISTS stories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_name TEXT NOT NULL UNIQUE,
        protagonistas TEXT NOT NULL,
        relator TEXT NOT NULL,
        sinopsis TEXT NOT NULL,
        escenarios TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `, (err) => {
      if (err) console.error('Error creating stories table:', err);
      else console.log('✓ Stories table ready');
    });

    // Tabla de reglas
    database.run(`
      CREATE TABLE IF NOT EXISTS reglas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        orden INTEGER NOT NULL,
        texto TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating reglas table:', err);
      else console.log('✓ Reglas table ready');
    });

    // Tabla de actos
    database.run(`
      CREATE TABLE IF NOT EXISTS actos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        story_id INTEGER NOT NULL,
        numero INTEGER NOT NULL,
        titulo TEXT NOT NULL,
        contenido TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE
      )
    `, (err) => {
      if (err) console.error('Error creating actos table:', err);
      else console.log('✓ Actos table ready');
    });
  });

  return database;
}

function closeDB() {
  if (db) {
    db.close((err) => {
      if (err) {
        console.error('Error closing database:', err);
      } else {
        console.log('Database closed');
      }
    });
    db = null;
  }
}

module.exports = { getDB, initializeDB, closeDB };
