-- Seed data: Insertar historia con beats pre-definidos
-- ID: <title_snake_case>_<timestamp_unix>
-- Uso: sqlite3 stories.db < scripts/sql/insert_story.sql

-- Insertar story
INSERT INTO story (id, title, protagonista, relator, escenarios, sinopsis, atmosfera, status, created_at)
VALUES (
    'el_monte_prohibido_1744742400',
    'El Monte Prohibido',
    'Carlos, Lucía y Marcos',
    'tercera_persona',
    'Un monte aislado en las afueras del pueblo',
    'Un grupo de amigos decide explorar el monte prohibido del pueblo. Lo que comienza como una aventura termina en una pesadilla.',
    'terror_psicologico',
    'pending',
    datetime('now')
);

-- Insertar beats pre-definidos (el LLM expandirá cada summary)
INSERT INTO beat (story_id, number, summary, status) VALUES
('el_monte_prohibido_1744742400', 1, 'Llegada al sendero', 'pending'),
('el_monte_prohibido_1744742400', 2, 'Primera señal: los pájaros callan', 'pending'),
('el_monte_prohibido_1744742400', 3, 'Encontrar señal antigua de advertencia', 'pending'),
('el_monte_prohibido_1744742400', 4, 'La primera desaparición del grupo', 'pending'),
('el_monte_prohibido_1744742400', 5, 'Escuchar voces en la oscuridad', 'pending'),
('el_monte_prohibido_1744742400', 6, 'Descubrir refugio abandonado', 'pending'),
('el_monte_prohibido_1744742400', 7, 'Revelación del oscuro pasado del monte', 'pending'),
('el_monte_prohibido_1744742400', 8, 'Persecución por fuerza invisible', 'pending'),
('el_monte_prohibido_1744742400', 9, 'Decisión final: quedarse o huir', 'pending'),
('el_monte_prohibido_1744742400', 10, 'El final: sacrificio o escape', 'pending');