import fs from "fs";
import path from "path";

/**
 * Spec-540 §2.3: de qué ambiente es esta UI y, en dev, en qué rama y commit está.
 *
 * `ENV=dev` activa la marca y el tema de dev; cualquier otro valor (o ninguno) es
 * prod, así prod y los E2E se ven como siempre. La rama y el commit se leen de
 * `.git/` sin el binario de git (el contenedor de dev lo monta en solo lectura).
 */
export interface Environment {
  env: "dev" | "prod";
  isDev: boolean;
  branch: string | null;
  commit: string | null;
}

interface GitVersion {
  branch: string | null;
  commit: string | null;
}

function read(file: string): string | null {
  try {
    return fs.readFileSync(file, "utf-8").trim();
  } catch {
    return null;
  }
}

function packedRef(gitDir: string, ref: string): string | null {
  const packed = read(path.join(gitDir, "packed-refs"));
  const line = packed?.split("\n").find((l) => l.endsWith(` ${ref}`));
  return line ? line.split(" ")[0] : null;
}

/** Rama y commit (7 caracteres) del repo en `gitDir`; nulos si no se pueden leer. */
export function readGitVersion(gitDir: string): GitVersion {
  const head = read(path.join(gitDir, "HEAD"));
  if (!head) return { branch: null, commit: null };

  if (!head.startsWith("ref: ")) return { branch: null, commit: head.slice(0, 7) }; // HEAD suelto

  const ref = head.slice(5);
  const sha = read(path.join(gitDir, ref)) ?? packedRef(gitDir, ref);
  return { branch: ref.replace(/^refs\/heads\//, ""), commit: sha ? sha.slice(0, 7) : null };
}

export function getEnvironment(
  env: string | undefined = process.env.ENV,
  gitDir: string = process.env.GIT_DIR ?? path.resolve(process.cwd(), "..", ".git"),
): Environment {
  if (env !== "dev") return { env: "prod", isDev: false, branch: null, commit: null };
  return { env: "dev", isDev: true, ...readGitVersion(gitDir) };
}
