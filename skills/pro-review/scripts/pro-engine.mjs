#!/usr/bin/env node
// OmO Pro Review - ChatGPT-Pro engine.
// Builds (plan) or runs (run) the guarded browser invocation that reaches the
// web-only Pro tier for one brief. Zero dependencies beyond the pinned transport.
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, linkSync, lstatSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, realpathSync, rmSync, statSync, unlinkSync, writeFileSync } from "node:fs";
import { randomBytes } from "node:crypto";
import os from "node:os";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { hazardReason, isOutside, PRO_MODEL, readManifestSafe, repoLinkOnPath, sha256, show, validateBrief } from "./handoff.mjs";
import { prepareInvocation } from "./oracle-guard.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const GUARD = join(here, "oracle-guard.mjs");
const ORACLE_PACKAGE = "@steipete/oracle";
const ORACLE_VERSION = "0.21.1";
const ORACLE_HOME = join(os.homedir(), ".oracle");
const PROFILE_DIR = join(ORACLE_HOME, "browser-profile");

function pinnedCliIn(packageRoot) {
  try {
    const info = JSON.parse(readFileSync(join(packageRoot, "package.json"), "utf8"));
    const cli = join(packageRoot, "dist/bin/oracle-cli.js");
    return info.name === ORACLE_PACKAGE && info.version === ORACLE_VERSION && existsSync(cli) ? cli : null;
  } catch {
    return null;
  }
}

/**
 * Locate the pinned transport: PRO_REVIEW_ORACLE_CLI, then the npx cache, then
 * the global npm root. The guard re-validates name, version and layout.
 */
export function resolveOracleCli(env = process.env, cwd = process.cwd()) {
  if (env.PRO_REVIEW_ORACLE_CLI) {
    if (!isAbsolute(env.PRO_REVIEW_ORACLE_CLI)) throw new Error("pro-review engine: PRO_REVIEW_ORACLE_CLI must be an absolute path");
    return env.PRO_REVIEW_ORACLE_CLI;
  }
  const home = env.HOME || env.USERPROFILE || os.homedir();
  // npm runs from the user's home, so a reviewed project's .npmrc can never pick
  // the executable transport; candidates inside the working project are refused too.
  const npm = (args) => {
    const result = spawnSync(process.platform === "win32" ? "npm.cmd" : "npm", args,
      { encoding: "utf8", env, cwd: home, timeout: 15000, shell: process.platform === "win32" });
    return result.status === 0 ? result.stdout.trim() : "";
  };
  let projectReal;
  try { projectReal = realpathSync(cwd); } catch { projectReal = undefined; }
  const inProject = (path) => {
    if (!projectReal || projectReal === realpathSync(home)) return false;
    try { return !isOutside(relative(projectReal, realpathSync(path))); } catch { return true; }
  };
  const defaultCache = process.platform === "win32" && env.LOCALAPPDATA ? join(env.LOCALAPPDATA, "npm-cache") : join(home, ".npm");
  // npm's effective cache: explicit env (either case), then npm's own config, then the platform default.
  const caches = [env.NPM_CONFIG_CACHE, env.npm_config_cache, npm(["config", "get", "cache"]), defaultCache]
    .filter((cache, index, all) => cache && isAbsolute(cache) && all.indexOf(cache) === index);
  const roots = [];
  for (const cache of caches) {
    try {
      for (const entry of readdirSync(join(cache, "_npx"))) roots.push(join(cache, "_npx", entry, "node_modules", ORACLE_PACKAGE));
    } catch { /* no npx cache there */ }
  }
  const globalRoot = npm(["root", "-g"]);
  if (globalRoot) roots.push(join(globalRoot, ORACLE_PACKAGE));
  for (const root of roots) {
    const cli = pinnedCliIn(root);
    if (cli && !inProject(cli)) return cli;
  }
  throw new Error("pro-review engine: " + ORACLE_PACKAGE + "@" + ORACLE_VERSION + " not found; install it with `npx -y " +
    ORACLE_PACKAGE + "@" + ORACLE_VERSION + " --version` or set PRO_REVIEW_ORACLE_CLI to its dist/bin/oracle-cli.js");
}

const SWITCHES = new Set(["preview", "prompt-only", "keep-browser"]);
const VALUES = new Set(["manifest", "brief", "report", "pass", "slug", "timeout"]);
function parseArgs(list) {
  const flags = {};
  for (let index = 0; index < list.length; index += 1) {
    const token = list[index];
    if (!token.startsWith("--")) throw new Error("pro-review engine: unexpected argument " + token);
    const key = token.slice(2);
    if (SWITCHES.has(key)) { flags[key] = true; continue; }
    if (!VALUES.has(key)) throw new Error("pro-review engine: unknown option --" + key);
    const value = list[index + 1];
    if (value === undefined || value.startsWith("--") || value === "") throw new Error("pro-review engine: --" + key + " requires a value");
    flags[key] = value;
    index += 1;
  }
  if (flags.pass !== undefined && !/^[1-9]\d*$/.test(flags.pass)) throw new Error("pro-review engine: --pass must be a positive integer");
  if (flags.timeout !== undefined && !/^\d+(ms|s|m|h)$/.test(flags.timeout)) throw new Error("pro-review engine: --timeout must look like 20m, 90s or 1h");
  return flags;
}

/**
 * Load a handoff manifest for one pass and re-validate every scoped file against
 * the plan: canonical containment, the shared path policy, regular-file type,
 * and the recorded content hash. Returns the verified bytes so the upload is a
 * snapshot of exactly what was approved, never a re-read of mutable paths.
 */
export function fromManifest(manifestPath, pass = 1) {
  const fail = (reason) => { throw new Error("pro-review engine: " + reason); };
  let manifest;
  try { manifest = readManifestSafe(manifestPath); } catch (error) { fail(error.message.replace(/^pro-review engine: /, "")); }
  if (manifest.engine?.mode !== "pro") {
    fail("manifest engine mode is " + (manifest.engine?.mode ?? "unknown") + ", not pro; use the client engine for that handoff");
  }
  if (manifest.engine.model !== undefined && manifest.engine.model !== PRO_MODEL) fail("manifest model " + manifest.engine.model + " is not the pinned " + PRO_MODEL);
  if (typeof manifest.repo !== "string" || !isAbsolute(manifest.repo)) fail("manifest repo must be an absolute path");
  const index = pass - 1;
  const scopePass = manifest.scope?.passes?.[index];
  if (!Array.isArray(scopePass) || scopePass.length === 0) fail("manifest has no pass " + pass);
  const rootReal = realpathSync(manifest.repo);
  // Before reading any dependent file: no repository link may redirect the
  // manifest, the brief or the report since planning.
  for (const path of [manifestPath, manifest.paths?.briefs?.[index], manifest.paths?.reports?.[index] ?? manifest.paths?.report]) {
    if (typeof path !== "string") continue;
    const redirect = repoLinkOnPath(path, rootReal);
    if (redirect) fail("a link inside the repository now redirects the handoff (" + redirect + "); re-plan into a real directory");
  }
  const verified = scopePass.map((file) => {
    const rel = file?.path;
    if (typeof rel !== "string" || isAbsolute(rel) || rel.split(/[\\/]/).includes("..")) fail("manifest path is not a plain repository-relative path: " + rel);
    if (typeof file.sha256 !== "string") fail("manifest predates content binding; re-plan the handoff");
    const policy = hazardReason(rel);
    if (policy) fail(rel + " is excluded by the path policy (" + policy + ")");
    let real;
    try { real = realpathSync(join(manifest.repo, rel)); } catch { fail(rel + " is missing or a dangling link"); }
    const canonicalRel = relative(rootReal, real).split(sep).join("/");
    if (canonicalRel === "" || isOutside(canonicalRel)) fail(rel + " now resolves outside the trusted root");
    const canonicalPolicy = hazardReason(canonicalRel);
    if (canonicalPolicy) fail(rel + " now resolves to an excluded path (" + canonicalPolicy + ")");
    if (!statSync(real).isFile()) fail(rel + " is not a regular file");
    const bytes = readFileSync(real);
    if (sha256(bytes) !== file.sha256) fail(rel + " changed since the handoff was planned; re-plan to approve the new content");
    return { path: rel, bytes };
  });
  // The brief becomes the prompt: it must be the regular file the plan wrote,
  // beside the manifest, with the bytes the plan recorded.
  let bound;
  try { bound = validateBrief(manifestPath, index); } catch (error) { fail(error.message); }
  const report = manifest.paths.reports?.[index] ?? manifest.paths.report;
  const files = verified.map((file) => join(manifest.repo, file.path));
  return { brief: bound.brief, prompt: bound.text, report, files, verified, rootReal, question: manifest.question, index };
}

/**
 * Write the verified bytes as ONE glob-safe text bundle in a private directory.
 * Repository filenames never reach the transport's pattern interface (a literal
 * `src/{a,b}.ts` would be brace-expanded and silently dropped); each file is
 * introduced by a `===== FILE: <path> =====` line. Nothing survives a failure.
 */
export function snapshot(verified) {
  const dir = mkdtempSync(join(os.tmpdir(), "pro-review-upload-"));
  try {
    chmodSync(dir, 0o700);
    const bundle = join(dir, "pro-review-bundle.txt");
    const parts = verified.map((file) => Buffer.concat([Buffer.from("===== FILE: " + file.path + " =====\n", "utf8"), file.bytes, Buffer.from("\n", "utf8")]));
    writeFileSync(bundle, Buffer.concat(parts), { flag: "wx", mode: 0o600 });
    return { dir, files: [bundle] };
  } catch (error) {
    rmSync(dir, { recursive: true, force: true });
    throw error;
  }
}

export function buildInvocation({ brief, prompt: verifiedPrompt, report, writeOutput, files = [], mode = "submit", slug, timeout = "20m", inputTimeout = "5m", keepBrowser = false }) {
  if (verifiedPrompt === undefined && (!brief || !existsSync(brief))) throw new Error("pro-review engine: brief file not found: " + brief);
  if (mode === "submit") {
    // lstat, not existsSync: a dangling link at the report path is an existing entry.
    let occupied = true;
    try { lstatSync(report); } catch { occupied = false; }
    if (occupied) throw new Error("pro-review engine: refusing to overwrite an existing report (or link) at " + report);
    const parent = lstatSync(dirname(resolve(report)));
    if (!parent.isDirectory() || parent.isSymbolicLink()) throw new Error("pro-review engine: the report directory must be a real directory: " + dirname(resolve(report)));
  }
  const prompt = verifiedPrompt ?? readFileSync(brief, "utf8");
  // Guard-level arguments: MODE first, then only the documented options.
  const guardArgs = [mode, "--prompt", prompt, "--files-report"];
  // The browser reviewer has no tools: every scoped file must ride as an upload.
  let largest = 0;
  for (const file of files) {
    if (!existsSync(file)) throw new Error("pro-review engine: scoped file missing: " + file);
    largest = Math.max(largest, statSync(file).size);
    guardArgs.push("--file", file);
  }
  // The single bundle can exceed the transport's 1 MiB per-file default even when
  // every repository file is small: size the transport limit to the real bundle.
  if (files.length > 0) guardArgs.push("--max-file-size-bytes", String(Math.max(1048576, largest + 1)));
  if (mode === "submit") {
    // The transport writes only to a private file; `run` publishes it with exclusive create.
    guardArgs.push("--write-output", resolve(writeOutput ?? report), "--browser-timeout", timeout,
      "--browser-input-timeout", inputTimeout, "--slug", slug ?? "omo pro review");
  }
  if (keepBrowser) guardArgs.push("--browser-keep-browser");
  const oracleCli = resolveOracleCli();
  const prepared = prepareInvocation({
    cli: oracleCli, home: ORACLE_HOME, profile: PROFILE_DIR, args: guardArgs, cwd: process.cwd(),
  });
  return {
    guard: GUARD,
    oracleCli,
    oracleHome: ORACLE_HOME,
    profileDir: PROFILE_DIR,
    args: prepared.args,
    guardArgs,
    env: prepared.env,
    promptChars: prompt.length,
    report: resolve(report),
    engine: { browser: true, model: "gpt-6-pro", thinkingTime: "pro", transport: "oracle-0.21.1" },
  };
}

/**
 * Publish a private reply to the report path with exclusive create. On ANY failure
 * (a link now on the path, an existing report, an unwritable directory) the reply
 * is copied to its own private directory first, so the caller can delete the upload.
 */
/**
 * Make `report` appear only fully written: write a private temp file in the same
 * directory, then hard-link it into place. link() is atomic and fails with EEXIST
 * rather than replacing anything; the temp file is always removed.
 */
export function publishAtomically(bytes, report) {
  const temp = join(dirname(report), ".pro-review-publish-" + randomBytes(6).toString("hex") + ".tmp");
  try {
    writeFileSync(temp, bytes, { flag: "wx", mode: 0o600 });
    linkSync(temp, report);
  } finally {
    try { unlinkSync(temp); } catch { /* never created */ }
  }
}
export function publishReply(privateReply, report, root) {
  const keep = (reason) => {
    try {
      const dir = mkdtempSync(join(os.tmpdir(), "pro-review-reply-"));
      chmodSync(dir, 0o700);
      writeFileSync(join(dir, "reply.md"), readFileSync(privateReply), { flag: "wx", mode: 0o600 });
      return { ok: false, reason, kept: join(dir, "reply.md") };
    } catch {
      // The backup itself failed: tell the caller to retain the original reply.
      return { ok: false, reason, kept: privateReply, retained: true };
    }
  };
  try {
    const redirect = root && repoLinkOnPath(report, root);
    if (redirect) return keep("a link inside the repository now redirects the report (" + redirect + ")");
    publishAtomically(readFileSync(privateReply), report);
    return { ok: true };
  } catch (error) {
    return keep("could not publish the report (" + (error?.code ?? "error") + ")");
  }
}

/**
 * Settle a finished transport run. Publish only after a successful exit; on a
 * failed or killed exit, preserve any reply already written instead of letting
 * the upload cleanup delete it. `retain` asks the caller to keep the upload dir.
 */
export function finishRun({ status, privateReply, report, root }) {
  const hasReply = Boolean(privateReply && existsSync(privateReply));
  if (status === 0) {
    if (!hasReply) return { code: 0 };
    const published = publishReply(privateReply, report, root);
    if (published.ok) return { code: 0 };
    return { code: 2, kept: published.kept, retain: Boolean(published.retained), message: published.reason + "; reply kept at " + published.kept };
  }
  const code = typeof status === "number" && status !== 0 ? status : 1;
  if (!hasReply) return { code };
  try {
    const dir = mkdtempSync(join(os.tmpdir(), "pro-review-reply-"));
    chmodSync(dir, 0o700);
    writeFileSync(join(dir, "reply.md"), readFileSync(privateReply), { flag: "wx", mode: 0o600 });
    return { code, kept: join(dir, "reply.md"), message: "the transport exited with a failure; its reply is kept at " + join(dir, "reply.md") };
  } catch {
    return { code, kept: privateReply, retain: true, message: "the transport exited with a failure; its reply is kept at " + privateReply };
  }
}

function main() {
  const [command, ...rest] = process.argv.slice(2);
  let flags;
  try {
    flags = parseArgs(rest);
  } catch (error) {
    console.error(show(error.message));
    return 2;
  }
  if (command !== "plan" && command !== "run") {
    console.error("usage: pro-engine.mjs plan|run --brief FILE --report FILE [--slug TEXT] [--timeout 20m]");
    return 2;
  }
  let invocation;
  let upload;
  let publishRoot;
  let retainReply = false;
  try {
    if (typeof flags.manifest !== "string" && flags["prompt-only"] !== true) {
      throw new Error("pro-review engine: --brief alone would upload no files; pass --manifest <file>, or --prompt-only for a prompt-only review");
    }
    if (typeof flags.manifest === "string") {
      const pass = Number(flags.pass ?? 1);
      const loaded = fromManifest(resolve(flags.manifest), pass);
      // `run` uploads a private snapshot of the verified bytes; `plan` only shows the repository paths.
      if (command === "run") upload = snapshot(loaded.verified);
      publishRoot = loaded.rootReal;
      invocation = buildInvocation({
        brief: loaded.brief, prompt: loaded.prompt, report: loaded.report, files: upload ? upload.files : loaded.files,
        writeOutput: upload ? join(upload.dir, "reply.md") : undefined,
        mode: flags.preview ? "preview" : "submit",
        slug: typeof flags.slug === "string" ? flags.slug : "omo pro review pass " + pass,
        timeout: typeof flags.timeout === "string" ? flags.timeout : "20m",
        keepBrowser: flags["keep-browser"] === true,
      });
    } else {
      // Prompt-only keeps the same filesystem protections, with the working
      // directory as the trusted root: the brief must be a regular non-link file
      // outside the path policy, and no repository link may sit on either path.
      if (typeof flags.brief !== "string" || typeof flags.report !== "string") throw new Error("pro-review engine: --prompt-only needs --brief FILE and --report FILE");
      const root = realpathSync(process.cwd());
      const briefPath = resolve(flags.brief);
      let briefStats;
      try { briefStats = lstatSync(briefPath); } catch { throw new Error("pro-review engine: brief file not found: " + briefPath); }
      if (!briefStats.isFile() || briefStats.size > 1 << 20) throw new Error("pro-review engine: the brief must be a regular file (not a link): " + briefPath);
      // The path policy applies wherever the brief lives, on the requested and canonical path.
      for (const absolute of [briefPath, realpathSync(briefPath)]) {
        const reason = hazardReason(absolute.split(sep).filter(Boolean).join("/"));
        if (reason) throw new Error("pro-review engine: the brief is excluded by the path policy (" + reason + ")");
      }
      for (const path of [briefPath, resolve(flags.report)]) {
        const redirect = repoLinkOnPath(path, root);
        if (redirect) throw new Error("pro-review engine: a link inside the working directory redirects " + path + " (" + redirect + ")");
      }
      publishRoot = root;
      if (command === "run") { upload = { dir: mkdtempSync(join(os.tmpdir(), "pro-review-upload-")), files: [] }; chmodSync(upload.dir, 0o700); }
      invocation = buildInvocation({
        brief: briefPath, prompt: readFileSync(briefPath, "utf8"), report: flags.report, mode: flags.preview ? "preview" : "submit",
        writeOutput: upload ? join(upload.dir, "reply.md") : undefined,
        slug: typeof flags.slug === "string" ? flags.slug : undefined,
        timeout: typeof flags.timeout === "string" ? flags.timeout : "20m",
        keepBrowser: flags["keep-browser"] === true,
      });
    }
  } catch (error) {
    if (upload) rmSync(upload.dir, { recursive: true, force: true });
    console.error(show(error.message));
    return 2;
  }
  if (command === "plan") {
    // Show the invocation shape, never the prompt body.
    const { env, ...visible } = invocation;
    const redact = (list) => list.map((value, index) => (list[index - 1] === "--prompt"
      ? "<prompt: " + value.length + " chars, sha256 " + sha256(Buffer.from(value, "utf8")).slice(0, 12) + ">" : value));
    console.log(JSON.stringify({ ...visible, args: redact(visible.args), guardArgs: redact(visible.guardArgs), envKeys: Object.keys(env).length }, null, 2));
    return 0;
  }
  try {
    const child = spawnSync(process.execPath,
      [GUARD, "--oracle-cli", invocation.oracleCli, "--oracle-home", ORACLE_HOME, "--profile-dir", PROFILE_DIR, ...invocation.guardArgs],
      { cwd: process.cwd(), env: invocation.env, stdio: "inherit" });
    const result = finishRun({ status: child.status, privateReply: upload ? join(upload.dir, "reply.md") : undefined,
      report: invocation.report, root: publishRoot });
    if (result.retain) retainReply = true;
    if (result.message) console.error(show("pro-review engine: " + result.message));
    return result.code;
  } finally {
    // Keep the private reply when neither publication nor its backup succeeded.
    if (upload && retainReply) for (const file of upload.files) rmSync(file, { force: true });
    else if (upload) rmSync(upload.dir, { recursive: true, force: true });
  }
}
if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) process.exit(main());
