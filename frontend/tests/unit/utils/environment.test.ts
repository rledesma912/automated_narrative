import fs from "fs";
import os from "os";
import path from "path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { getEnvironment, readGitVersion } from "../../../src/utils/environment";

/** Spec-540 T1.1: ambiente de la UI y versión de git para la marca de dev. */
const SHA = "4bdebc3f0a1b2c3d4e5f60718293a4b5c6d7e8f9";
let gitDir: string;

function write(rel: string, content: string) {
  const file = path.join(gitDir, rel);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
}

beforeEach(() => {
  gitDir = fs.mkdtempSync(path.join(os.tmpdir(), "git-"));
});

afterEach(() => {
  fs.rmSync(gitDir, { recursive: true, force: true });
});

describe("readGitVersion", () => {
  it("lee la rama y el commit de un ref suelto", () => {
    write("HEAD", "ref: refs/heads/feat/spec-540\n");
    write("refs/heads/feat/spec-540", `${SHA}\n`);
    expect(readGitVersion(gitDir)).toEqual({ branch: "feat/spec-540", commit: "4bdebc3" });
  });

  it("busca el commit en packed-refs si el ref no está suelto", () => {
    write("HEAD", "ref: refs/heads/development\n");
    write("packed-refs", `# pack-refs with: peeled\n${SHA} refs/heads/development\n`);
    expect(readGitVersion(gitDir)).toEqual({ branch: "development", commit: "4bdebc3" });
  });

  it("con HEAD suelto da solo el commit", () => {
    write("HEAD", `${SHA}\n`);
    expect(readGitVersion(gitDir)).toEqual({ branch: null, commit: "4bdebc3" });
  });

  it("sin .git legible devuelve nulos sin fallar", () => {
    expect(readGitVersion(path.join(gitDir, "no-existe"))).toEqual({ branch: null, commit: null });
  });

  it("rama sin commits todavía: rama sí, commit no", () => {
    write("HEAD", "ref: refs/heads/nueva\n");
    expect(readGitVersion(gitDir)).toEqual({ branch: "nueva", commit: null });
  });
});

describe("getEnvironment", () => {
  it.each([undefined, "", "prod", "production", "DEV"])("ENV=%s es prod, sin versión", (env) => {
    write("HEAD", `${SHA}\n`);
    expect(getEnvironment(env, gitDir)).toEqual({ env: "prod", isDev: false, branch: null, commit: null });
  });

  it("ENV=dev trae rama y commit", () => {
    write("HEAD", "ref: refs/heads/main\n");
    write("refs/heads/main", SHA);
    expect(getEnvironment("dev", gitDir)).toEqual({ env: "dev", isDev: true, branch: "main", commit: "4bdebc3" });
  });
});
