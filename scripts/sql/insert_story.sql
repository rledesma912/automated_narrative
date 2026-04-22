-- Seed data: historia de ejemplo con 5 macro-beats (Spec-038)
-- Uso: sqlite3 stories.db < scripts/sql/insert_story.sql

-- Escenarios cronológicos
INSERT INTO scenario (id, story_id, order_index, name) VALUES
    ('escenario_monte_1', 'el_monte_prohibido_1744742400', 1, 'La casa de la abuela María'),
    ('escenario_monte_2', 'el_monte_prohibido_1744742400', 2, 'La estancia de la fiesta'),
    ('escenario_monte_3', 'el_monte_prohibido_1744742400', 3, 'El camino de regreso'),
    ('escenario_monte_4', 'el_monte_prohibido_1744742400', 4, 'El Monte Prohibido'),
    ('escenario_monte_5', 'el_monte_prohibido_1744742400', 5, 'La salida del monte al amanecer');

-- Historia principal
INSERT INTO story (id, title, protagonista, relator, escenarios, sinopsis, atmosfera, status, created_at)
VALUES (
    'el_monte_prohibido_1744742400',
    'El Monte Prohibido',
    'Ricardo (padre escéptico), Irene (madre creyente), Mariano (hijo valiente), Soledad (bebé), María (abuela supersticiosa)',
    'Irene',
    'La casa de campo de la abuela María / La estancia de la fiesta / El camino de regreso / El Monte Prohibido',
    'Una familia visita la casa de María en una zona rural aislada. Tras ignorar la advertencia de evitar el Monte Prohibido al regresar de una fiesta, se ven atrapados en una tormenta y forzados a cruzarlo. La oscuridad se vuelve densa y opresiva. Solo la fe de Irene logra abrirles camino hacia la salida al amanecer.',
    'terror paranormal, terror folclórico, leyendas de campo',
    'pending',
    datetime('now')
);

-- 5 macro-beats (estructura de 5 actos, Spec-038)
-- narrative_context y memory_snapshot son generados por el pipeline LLM; quedan vacíos en el seed
INSERT INTO macro_beat (story_id, number, summary, status, active_scenario_id, narrative_context, memory_snapshot) VALUES
    ('el_monte_prohibido_1744742400', 1, 'La abuela María advierte a la familia sobre el Monte Prohibido antes de que partan a la fiesta.', 'pending', 'escenario_monte_1', NULL, NULL),
    ('el_monte_prohibido_1744742400', 2, 'La familia disfruta la fiesta en la estancia; el tiempo se escurre hasta que la tormenta los sorprende al partir.', 'pending', 'escenario_monte_2', NULL, NULL),
    ('el_monte_prohibido_1744742400', 3, 'El caballo rehúsa el camino habitual; la tormenta los obliga a internarse en el Monte Prohibido.', 'pending', 'escenario_monte_3', NULL, NULL),
    ('el_monte_prohibido_1744742400', 4, 'La oscuridad del monte cobra vida: susurros, sombras y presencias invisibles acechan a la familia.', 'pending', 'escenario_monte_4', NULL, NULL),
    ('el_monte_prohibido_1744742400', 5, 'Las oraciones de Irene abren un camino de salida; la familia emerge al amanecer marcada para siempre.', 'pending', 'escenario_monte_5', NULL, NULL);
