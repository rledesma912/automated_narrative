-- Seed data: Insertar historia con beats pre-definidos
-- ID: <title_snake_case>_<timestamp_unix>
-- Uso: sqlite3 stories.db < scripts/sql/insert_story.sql

-- Insertar story
INSERT INTO story (id, title, protagonista, relator, escenarios, sinopsis, atmosfera, status, created_at)
VALUES (
    'el_monte_prohibido_1744742400',
    'El Monte Prohibido',
    'Ricardo (padre escéptico), Irene (madre creyente), Mariano (hijo valiente), Soledad (bebé), María (abuela supersticiosa)',
    'Irene',
    'La casa de campo de la abuela María, la casa de campo donde ocurre la fiesta, un camino desolado, nocturno y con llovizna, un monte siniestro y oscuro.',
    'Una familia visita la casa de María en una zona rural aislada. Tras ignorar la advertencia de evitar el "Monte Prohibido" al regresar de una fiesta, se ven atrapados en una tormenta y forzados a cruzarlo. Allí, la oscuridad se vuelve densa y opresiva, rodeándolos de sombras y susurros sobrenaturales. Solo la fe y las oraciones de Irene logran abrirles camino hacia la salida al amanecer, dejando una marca imborrable en sus vidas.',
    'terror paranormal, terror folclorico, leyendas de campo.',
    'pending',
    datetime('now')
);

-- Insertar beats pre-definidos (el LLM expandirá cada summary)
INSERT INTO beat (story_id, number, summary, status) VALUES
('el_monte_prohibido_1744742400', 1, 'La abuela María lanza una advertencia inquietante sobre el Monte Prohibido antes de la partida.', 'pending'),
('el_monte_prohibido_1744742400', 2, 'Preparación de la familia y el viaje inicial en sulky hacia la fiesta en la estancia cercana.', 'pending'),
('el_monte_prohibido_1744742400', 3, 'La fiesta en la estancia: risas, música y cómo el tiempo se les escurre sin que se den cuenta.', 'pending'),
('el_monte_prohibido_1744742400', 4, 'Emprenden el regreso bajo una tormenta que comienza a desatarse, oscureciendo el camino.', 'pending'),
('el_monte_prohibido_1744742400', 5, 'El caballo se vuelve inquieto y obstinado, obligándolos a tomar el atajo por el monte prohibido.', 'pending'),
('el_monte_prohibido_1744742400', 6, 'La entrada al monte: la oscuridad se vuelve densa, opresiva y las sombras parecen cobrar vida propia.', 'pending'),
('el_monte_prohibido_1744742400', 7, 'El miedo erosiona la razón: susurros sin origen y presencias invisibles acechan a la familia.', 'pending'),
('el_monte_prohibido_1744742400', 8, 'Refugio en la fe: Irene comienza a rezar fervientemente las oraciones y rituales aprendidos de su abuela.', 'pending'),
('el_monte_prohibido_1744742400', 9, 'Las manifestaciones sobrenaturales retroceden ante las palabras de fe, abriendo un camino de salida.', 'pending'),
('el_monte_prohibido_1744742400', 10, 'Llegada del amanecer y abandono del monte: el impacto psicológico y la marca imborrable en la familia.', 'pending');
