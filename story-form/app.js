const express = require('express');
const path    = require('path');
const storyRoutes = require('./routes/story');

const app = express();
const PORT = process.env.PORT || 3100;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

app.use('/', storyRoutes);

app.listen(PORT, () => {
  console.log(`✦ Story Form corriendo en http://localhost:${PORT}`);
});