import { describe, it, expect, afterEach } from "vitest";
import fs from "fs";
import os from "os";
import path from "path";
import { assetVersion } from "../../../src/utils/assets";

/** Spec-630 B17: la versión cambia cuando cambian los estáticos, no en cada reinicio. */
function publicDir(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "assets-"));
  fs.mkdirSync(path.join(dir, "js"));
  fs.writeFileSync(path.join(dir, "styles.css"), "a{}");
  fs.writeFileSync(path.join(dir, "js", "x.js"), "1");
  const old = new Date("2026-10-01T10:00:00Z");
  fs.utimesSync(path.join(dir, "styles.css"), old, old);
  fs.utimesSync(path.join(dir, "js", "x.js"), old, old);
  return dir;
}

afterEach(() => {
  delete process.env.ASSET_VERSION;
});

describe("assetVersion", () => {
  it("es estable si nada cambia y cambia si cambia el CSS o un script", () => {
    const dir = publicDir();
    const v1 = assetVersion(dir);
    expect(assetVersion(dir)).toBe(v1);

    const later = new Date("2026-10-02T10:00:00Z");
    fs.utimesSync(path.join(dir, "styles.css"), later, later);
    const v2 = assetVersion(dir);
    expect(v2).not.toBe(v1);

    fs.utimesSync(path.join(dir, "js", "x.js"), new Date("2026-10-03T10:00:00Z"), new Date("2026-10-03T10:00:00Z"));
    expect(assetVersion(dir)).not.toBe(v2);
  });

  it("ASSET_VERSION la fija a mano", () => {
    process.env.ASSET_VERSION = "fija";
    expect(assetVersion(publicDir())).toBe("fija");
  });
});
