import fs from "fs";
import path from "path";

const PUBLIC = path.join(__dirname, "..", "..", "public");

/**
 * Spec-630 B17: versión de los estáticos (`/styles.css?v=…`, `/js/x.js?v=…` y el
 * `<meta name="asset-version">`). Sale de la última modificación de `styles.css`
 * y de `public/js/`: cambia cuando cambian (en dev, cuando tailwind recompila; en
 * prod, con cada deploy) y no en cada reinicio. ASSET_VERSION la fija a mano.
 */
export function assetVersion(dir: string = PUBLIC): string {
  if (process.env.ASSET_VERSION) return process.env.ASSET_VERSION;
  const files = [path.join(dir, "styles.css")];
  try {
    for (const f of fs.readdirSync(path.join(dir, "js"))) if (f.endsWith(".js")) files.push(path.join(dir, "js", f));
  } catch {
    /* sin public/js */
  }
  let newest = 0;
  for (const f of files) {
    try {
      newest = Math.max(newest, fs.statSync(f).mtimeMs);
    } catch {
      /* todavía no compilado */
    }
  }
  return Math.floor(newest).toString(36);
}
