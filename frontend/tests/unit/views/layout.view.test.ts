import { readFileSync } from "fs";
import path from "path";
import { describe, it, expect } from "vitest";

const layoutPath = path.join(process.cwd(), "src/views/partials/layout.ejs");

describe("layout view", () => {
  // Spec-510 T1.2: el banner usa window.ForgeEta; los scripts defer respetan el orden.
  it("loads eta.js before generation-banner.js", () => {
    const template = readFileSync(layoutPath, "utf-8");
    const scripts = Array.from(
      template.matchAll(/<script src="\/js\/([\w-]+)\.js\?v=[^"]*" defer><\/script>/g),
      (m) => m[1],
    );

    expect(scripts).toContain("eta");
    expect(scripts.indexOf("eta")).toBeLessThan(scripts.indexOf("generation-banner"));
  });
});
