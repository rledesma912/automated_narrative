const express = require('express');

const app = express();
const PORT = 8080;

app.use(express.static('public'));

app.get('/', (req, res) => {
  res.redirect('/sinopsis.html');
});

app.listen(PORT, () => {
  console.log(`Servidor corriendo en http://localhost:${PORT}`);
});