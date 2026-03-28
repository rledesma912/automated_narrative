const { getDB } = require('../db/init');

class Story {
  static async create(data) {
    const db = getDB();
    return new Promise((resolve, reject) => {
      const {
        story_name,
        protagonistas,
        relator,
        sinopsis,
        escenarios,
        reglas,
        acto1, acto2, acto3, acto4, acto5
      } = data;

      db.run(
        `INSERT INTO stories (story_name, protagonistas, relator, sinopsis, escenarios)
         VALUES (?, ?, ?, ?, ?)`,
        [story_name, protagonistas, relator, sinopsis, escenarios],
        function(err) {
          if (err) {
            console.error('Error inserting story:', err);
            reject(err);
            return;
          }

          const storyId = this.lastID;
          let completed = 0;
          let hasError = false;

          // Procesar reglas
          const reglasList = Array.isArray(reglas)
            ? reglas.filter(r => r && r.trim())
            : (reglas ? reglas.split('\n').filter(r => r && r.trim()) : []);

          // Preparar lista de operaciones
          const operations = [];

          // Agregar reglas a operaciones
          reglasList.forEach((texto, index) => {
            operations.push({
              type: 'regla',
              data: [storyId, index + 1, texto.trim()]
            });
          });

          // Agregar actos a operaciones
          const acts = [
            { numero: 1, titulo: 'Situación inicial', contenido: acto1 },
            { numero: 2, titulo: 'Conflicto inicial', contenido: acto2 },
            { numero: 3, titulo: 'Falsa calma', contenido: acto3 },
            { numero: 4, titulo: 'Crisis mayor', contenido: acto4 },
            { numero: 5, titulo: 'Clímax y resolución', contenido: acto5 }
          ];

          acts.forEach(act => {
            operations.push({
              type: 'acto',
              data: [storyId, act.numero, act.titulo, act.contenido]
            });
          });

          const totalOps = operations.length;

          if (totalOps === 0) {
            resolve({ id: storyId, story_name });
            return;
          }

          // Ejecutar todas las operaciones
          operations.forEach(op => {
            if (op.type === 'regla') {
              db.run(
                `INSERT INTO reglas (story_id, orden, texto) VALUES (?, ?, ?)`,
                op.data,
                (err) => {
                  if (err && !hasError) {
                    hasError = true;
                    console.error('Error inserting regla:', err);
                    reject(err);
                    return;
                  }
                  completed++;
                  if (completed === totalOps && !hasError) {
                    resolve({ id: storyId, story_name });
                  }
                }
              );
            } else if (op.type === 'acto') {
              db.run(
                `INSERT INTO actos (story_id, numero, titulo, contenido) VALUES (?, ?, ?, ?)`,
                op.data,
                (err) => {
                  if (err && !hasError) {
                    hasError = true;
                    console.error('Error inserting acto:', err);
                    reject(err);
                    return;
                  }
                  completed++;
                  if (completed === totalOps && !hasError) {
                    resolve({ id: storyId, story_name });
                  }
                }
              );
            }
          });
        }
      );
    });
  }

  static async findById(id) {
    const db = getDB();
    return new Promise((resolve, reject) => {
      db.get(
        `SELECT * FROM stories WHERE id = ?`,
        [id],
        async (err, story) => {
          if (err) {
            reject(err);
            return;
          }

          if (!story) {
            resolve(null);
            return;
          }

          // Obtener reglas
          db.all(
            `SELECT * FROM reglas WHERE story_id = ? ORDER BY orden`,
            [id],
            (err, reglas) => {
              if (err) {
                reject(err);
                return;
              }

              // Obtener actos
              db.all(
                `SELECT * FROM actos WHERE story_id = ? ORDER BY numero`,
                [id],
                (err, actos) => {
                  if (err) {
                    reject(err);
                    return;
                  }

                  resolve({
                    ...story,
                    reglas: reglas || [],
                    actos: actos || []
                  });
                }
              );
            }
          );
        }
      );
    });
  }

  static async findAll() {
    const db = getDB();
    return new Promise((resolve, reject) => {
      db.all(
        `SELECT id, story_name, created_at, updated_at FROM stories ORDER BY updated_at DESC`,
        [],
        (err, stories) => {
          if (err) {
            reject(err);
          } else {
            resolve(stories || []);
          }
        }
      );
    });
  }

  static async update(id, data) {
    const db = getDB();
    return new Promise((resolve, reject) => {
      const {
        story_name,
        protagonistas,
        relator,
        sinopsis,
        escenarios,
        reglas,
        acto1, acto2, acto3, acto4, acto5
      } = data;

      db.run(
        `UPDATE stories SET story_name = ?, protagonistas = ?, relator = ?, sinopsis = ?, escenarios = ?, updated_at = CURRENT_TIMESTAMP
         WHERE id = ?`,
        [story_name, protagonistas, relator, sinopsis, escenarios, id],
        function(err) {
          if (err) {
            console.error('Error updating story:', err);
            reject(err);
            return;
          }

          // Limpiar reglas y actos
          let deleteOps = 0;
          const deleteTotal = 2;

          db.run(`DELETE FROM reglas WHERE story_id = ?`, [id], (err) => {
            if (err) {
              console.error('Error deleting reglas:', err);
              reject(err);
              return;
            }
            deleteOps++;
            if (deleteOps === deleteTotal) {
              insertNewData();
            }
          });

          db.run(`DELETE FROM actos WHERE story_id = ?`, [id], (err) => {
            if (err) {
              console.error('Error deleting actos:', err);
              reject(err);
              return;
            }
            deleteOps++;
            if (deleteOps === deleteTotal) {
              insertNewData();
            }
          });

          function insertNewData() {
            // Procesar reglas
            const reglasList = Array.isArray(reglas)
              ? reglas.filter(r => r && r.trim())
              : (reglas ? reglas.split('\n').filter(r => r && r.trim()) : []);

            // Preparar operaciones
            const operations = [];

            // Agregar reglas
            reglasList.forEach((texto, index) => {
              operations.push({
                type: 'regla',
                data: [id, index + 1, texto.trim()]
              });
            });

            // Agregar actos
            const acts = [
              { numero: 1, titulo: 'Situación inicial', contenido: acto1 },
              { numero: 2, titulo: 'Conflicto inicial', contenido: acto2 },
              { numero: 3, titulo: 'Falsa calma', contenido: acto3 },
              { numero: 4, titulo: 'Crisis mayor', contenido: acto4 },
              { numero: 5, titulo: 'Clímax y resolución', contenido: acto5 }
            ];

            acts.forEach(act => {
              operations.push({
                type: 'acto',
                data: [id, act.numero, act.titulo, act.contenido]
              });
            });

            const totalOps = operations.length;

            if (totalOps === 0) {
              resolve({ id, story_name });
              return;
            }

            let completed = 0;
            let hasError = false;

            // Ejecutar todas las operaciones
            operations.forEach(op => {
              if (op.type === 'regla') {
                db.run(
                  `INSERT INTO reglas (story_id, orden, texto) VALUES (?, ?, ?)`,
                  op.data,
                  (err) => {
                    if (err && !hasError) {
                      hasError = true;
                      console.error('Error inserting regla:', err);
                      reject(err);
                      return;
                    }
                    completed++;
                    if (completed === totalOps && !hasError) {
                      resolve({ id, story_name });
                    }
                  }
                );
              } else if (op.type === 'acto') {
                db.run(
                  `INSERT INTO actos (story_id, numero, titulo, contenido) VALUES (?, ?, ?, ?)`,
                  op.data,
                  (err) => {
                    if (err && !hasError) {
                      hasError = true;
                      console.error('Error inserting acto:', err);
                      reject(err);
                      return;
                    }
                    completed++;
                    if (completed === totalOps && !hasError) {
                      resolve({ id, story_name });
                    }
                  }
                );
              }
            });
          }
        }
      );
    });
  }

  static async delete(id) {
    const db = getDB();
    return new Promise((resolve, reject) => {
      db.run(`DELETE FROM stories WHERE id = ?`, [id], function(err) {
        if (err) {
          reject(err);
        } else {
          resolve({ deleted: this.changes });
        }
      });
    });
  }
}

module.exports = Story;
