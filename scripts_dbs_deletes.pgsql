-- Delete cascade story information

delete from story_state;
delete from story_acts;
delete from stories;

-- Delete cascade tables
drop table if exists story_state;
drop table if exists story_acts;
drop table if exists stories;