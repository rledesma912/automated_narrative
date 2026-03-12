--script creación de tablas en PostgreSQL

CREATE TABLE stories (
  id_story TEXT PRIMARY KEY,
  story_name TEXT,
  total_acts INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE story_acts (
  id SERIAL PRIMARY KEY,
  id_story TEXT REFERENCES stories(id_story),
  act_number INTEGER,
  arc_phase TEXT,
  chapter TEXT,
  summary TEXT,
  memory TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_story_acts_story
ON story_acts (id_story, act_number);


