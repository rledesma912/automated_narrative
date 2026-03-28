require('dotenv').config();
const express = require('express');
const path    = require('path');
const storyRoutes = require('./routes/story');
const { initializeDB } = require('./db/init');

const app = express();
const PORT = process.env.PORT || 3100;

// Inicializar base de datos
initializeDB();

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Rutas
app.use('/', storyRoutes);

app.listen(PORT, () => {
  console.log(`✦ Story Form corriendo en http://localhost:${PORT}`);
  console.log(`✦ Listado de historias: http://localhost:${PORT}/list`);
});