import "dotenv/config";
import app from "./app";

const PORT = parseInt(process.env.PORT ?? "3000", 10);

app.listen(PORT, () => {
  console.log(`NarrativeForge UI  →  http://localhost:${PORT}`);
  console.log(`Core API target    →  ${process.env.CORE_API_URL ?? "http://localhost:8010"}`);
  console.log(`Debug panel        →  http://localhost:${PORT}/debug`);
});
