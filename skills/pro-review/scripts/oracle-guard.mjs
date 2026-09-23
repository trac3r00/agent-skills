#!/usr/bin/env node
// OmO Pro Review - ChatGPT-Pro transport guard.
// Refuses ambient, dotenv, CLI, config-file, and saved-session cookie sources
// before the pinned browser transport runs, and pins the Pro model + effort.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const cookieEnvKeys = ["ORACLE_BROWSER_COOKIES_JSON", "ORACLE_BROWSER_COOKIES_FILE"];
const fail = (reason) => { throw new Error("pro-review guard: " + reason); };
// The only project-dotenv settings promoted into the transport: audited, non-destructive
// tuning. Anything else (e.g. ORACLE_PERF_TRACE, an output path) is never promoted.
const PROMOTABLE = new Set(["ORACLE_HOME_DIR", "ORACLE_BROWSER_PROFILE_DIR", "ORACLE_BROWSER_ATTACHMENT_TIMEOUT",
  "ORACLE_BROWSER_APPROVAL_WAIT", "ORACLE_BROWSER_MAX_CONCURRENT_TABS"]);
const PROMPT_KEYS = ["promptSuffix", "promptPrefix", "systemPrompt"];
const NEW_CHAT_URL = "https://chatgpt.com/";
const RUNTIME_CONTROLS = new RegExp("^(?:NODE_OPTIONS|NODE_PATH|NODE_EXTRA_CA_CERTS|NODE_TLS_REJECT_UNAUTHORIZED|" +
  "LD_[A-Z0-9_]+|DYLD_[A-Z0-9_]+|PATH|HOME|USERPROFILE|SHELL|BASH_ENV|ENV|CHROME_PATH|BROWSER|PUPPETEER_[A-Z0-9_]+|" +
  "ORACLE_CLIENT_FACTORY|ORACLE_CHROME_NO_SANDBOX|ORACLE_BROWSER_REMOTE_DEBUG_HOST|ORACLE_BROWSER_PORT|" +
  "ORACLE_BROWSER_DEBUG_PORT|ORACLE_DEBUG_COOKIES|ORACLE_BROWSER_COOKIE_NAMES|ORACLE_BROWSER_ALLOW_COOKIE_ERRORS)$", "i");

function checkEnvironment(env) {
  if (cookieEnvKeys.some((key) => Object.hasOwn(env, key))) {
    fail("cookie environment configuration is forbidden (including empty values).");
  }
  if (env.DOTENV_KEY || env.DOTENV_CONFIG_DOTENV_KEY) {
    fail("encrypted dotenv is unsupported; use a cookie-free plaintext dotenv file.");
  }
  if (env.ORACLE_REMOTE_HOST || env.ORACLE_REMOTE_TOKEN || env.ORACLE_FORCE_TUI === "1") {
    fail("remote browser and forced TUI configuration are unsupported.");
  }
}

function readOptional(file) {
  try {
    return fs.readFileSync(file, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return undefined;
    fail("a preflight configuration file could not be read.");
  }
}

function checkConfig(value) {
  if (!value || typeof value !== "object") return;
  for (const [key, entry] of Object.entries(value)) {
    if ((/^(?:browser)?inlinecookies(?:file|source)?$/i.test(key) ||
         cookieEnvKeys.includes(key) || key === "chromeCookiePath" ||
         key === "browserCookiePath") && entry != null) {
      fail("cookie payload/export configuration is forbidden.");
    }
    if ((['cookieSync', 'manualLoginCookieSync', 'browserCookieSync',
      'browserManualLoginCookieSync', 'attachRunning'].includes(key) && entry === true) ||
      (['remoteChrome', 'remoteHost', 'copyProfileSource'].includes(key) && entry != null)) {
      fail("cookie synchronization, copied profiles, and remote/attached browsers are forbidden.");
    }
    if (PROMPT_KEYS.includes(key) && entry != null && entry !== "") {
      fail("prompt-mutating transport configuration (" + key + ") is forbidden: the approved brief is the whole prompt.");
    }
    checkConfig(entry);
  }
}

function checkAutoCookies(home) {
  for (const name of ["cookies.json", "cookies.base64"]) {
    try {
      fs.lstatSync(path.join(home, name));
      fail("an automatic cookie export exists in the effective Pro-transport home.");
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
    }
  }
}

function parseOptions(args, values, switches) {
  const result = [];
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    const equals = arg.indexOf("=");
    const key = equals < 0 ? arg : arg.slice(0, equals);
    if (values.includes(key)) {
      const value = equals < 0 ? args[++index] : arg.slice(equals + 1);
      if (value === undefined) fail("an option is missing its value.");
      result.push(key, value);
    } else if (switches.includes(key) && equals < 0) {
      result.push(key);
    } else {
      fail("unsupported option or command; use the documented protected interface.");
    }
  }
  return result;
}

/** Prepare without importing the transport CLI or performing browser/prompt actions. */
export function prepareInvocation({ cli, home, profile, args, cwd = process.cwd(), env = process.env }) {
  if (args.some((arg) => /^dotenv_config_(encoding|path|quiet|debug|override|DOTENV_KEY)=/.test(arg))) {
    fail("dotenv CLI assignments are unsupported; select dotenv through the invocation environment.");
  }
  if (![cli, home, profile].every((value) => typeof value === "string" && path.isAbsolute(value))) {
    fail("--oracle-cli, --oracle-home and --profile-dir must be absolute paths.");
  }
  cli = fs.realpathSync(cli);
  const packageRoot = path.resolve(path.dirname(cli), "../..");
  const packageInfo = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));
  if (packageInfo.name !== "@steipete/oracle" || packageInfo.version !== "0.21.1" ||
      cli !== path.join(packageRoot, "dist/bin/oracle-cli.js")) {
    fail("the transport must be the installed @steipete/oracle 0.21.1 dist/bin/oracle-cli.js.");
  }
  const require = createRequire(cli);
  const dotenv = require("dotenv");
  const JSON5 = require("json5");
  checkEnvironment(env);
  const effectiveEnv = { ...env };
  const dotenvPath = env.DOTENV_CONFIG_PATH
    ? (env.DOTENV_CONFIG_PATH.startsWith("~")
      ? path.join(env.HOME || os.homedir(), env.DOTENV_CONFIG_PATH.slice(1))
      : path.resolve(cwd, env.DOTENV_CONFIG_PATH))
    : path.join(cwd, ".env");
  let dotenvText;
  try {
    dotenvText = fs.readFileSync(dotenvPath, { encoding: env.DOTENV_CONFIG_ENCODING || "utf8" });
  } catch (error) {
    if (error.code !== "ENOENT") fail("dotenv preflight could not read the selected file.");
  }
  const parsedEnv = dotenv.parse(dotenvText ?? "");
  checkEnvironment(parsedEnv);
  // A project dotenv is repository content: it may tune the transport, never the
  // runtime that executes it. Loader, preload and browser-binary controls are
  // refused outright; everything outside the transport's own namespace is dropped.
  const control = Object.keys(parsedEnv).find((key) => RUNTIME_CONTROLS.test(key));
  if (control) fail("the project dotenv sets a runtime or browser control (" + control + "); remove it before a Pro review.");
  const promoted = Object.fromEntries(Object.entries(parsedEnv).filter(([key]) => PROMOTABLE.has(key)));
  dotenv.populate(effectiveEnv, promoted, { override: env.DOTENV_CONFIG_OVERRIDE, debug: false });
  checkEnvironment(effectiveEnv);
  home = path.resolve(home);
  profile = path.resolve(profile);
  const effectiveHome = path.resolve(cwd,
    effectiveEnv.ORACLE_HOME_DIR ?? path.join(effectiveEnv.HOME || os.homedir(), ".oracle"));
  checkAutoCookies(effectiveHome);
  checkAutoCookies(home);
  if (effectiveHome !== home) fail("effective Pro-transport home differs from --oracle-home.");
  if (effectiveEnv.ORACLE_BROWSER_PROFILE_DIR &&
      path.resolve(cwd, effectiveEnv.ORACLE_BROWSER_PROFILE_DIR) !== profile) {
    fail("ambient browser profile differs from --profile-dir.");
  }

  const configs = new Set([path.join(home, "config.json")]);
  const userHome = path.resolve(effectiveEnv.HOME || os.homedir());
  for (let current = path.resolve(cwd); current !== userHome; current = path.dirname(current)) {
    configs.add(path.join(current, ".oracle/config.json"));
    if (path.dirname(current) === current) break;
  }
  for (const file of configs) {
    const text = readOptional(file);
    if (text === undefined) continue;
    let config;
    try { config = JSON5.parse(text); } catch { fail("Pro-transport configuration is not valid JSON5."); }
    checkConfig(config);
    // A configured destination could drop a "fresh" review into an existing
    // conversation, project or custom GPT; the guard pins the new-chat URL itself.
    for (const destination of [config?.chatgptUrl, config?.url, config?.browser?.chatgptUrl, config?.browser?.url]) {
      if (destination != null && destination !== "") fail("configured ChatGPT destinations (chatgptUrl/url) are forbidden: every review starts a new chat.");
    }
    if (config?.browser?.manualLoginProfileDir &&
        path.resolve(cwd, config.browser.manualLoginProfileDir) !== profile) {
      fail("configured browser profile differs from --profile-dir.");
    }
  }

  const [mode, ...remaining] = args;
  let oracleArgs;
  if (mode === "preview" || mode === "submit") {
    const supplied = parseOptions(remaining,
      ["--prompt", "--file", "--slug", "--write-output", "--browser-timeout",
        "--browser-input-timeout", "--max-file-size-bytes"],
      ["--files-report", "--browser-keep-browser", "--verbose"]);
    oracleArgs = [
      "--engine", "browser", "--model", "gpt-6-pro",
      "--browser-model-strategy", "select", "--browser-thinking-time", "pro",
      "--browser-manual-login", "--browser-manual-login-profile-dir", profile,
      "--browser-no-cookie-sync", "--browser-archive", "never",
      "--browser-attachments", "always", "--browser-bundle-format", "text",
      "--chatgpt-url", NEW_CHAT_URL,
      ...(mode === "preview" ? ["--dry-run", "json"] : ["--wait"]),
      ...supplied,
    ];
  } else if (mode === "status") {
    oracleArgs = ["status", ...parseOptions(remaining, ["--hours", "--limit"], ["--all"])];
  } else if (mode === "session") {
    const [id, ...options] = remaining;
    if (!id || !/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(id)) {
      fail("recovery requires an exact saved session ID, not an alias or path.");
    }
    const dir = path.join(home, "sessions", id);
    const text = readOptional(path.join(dir, "meta.json"));
    if (text === undefined) fail("recovery requires modern saved session metadata.");
    let meta;
    try { meta = JSON.parse(text); } catch { fail("saved session metadata is not valid JSON."); }
    checkConfig(meta);
    if (meta.id !== id || typeof meta.status !== "string" || !meta.status) {
      fail("modern session identity/status is invalid; legacy fallback is unsupported.");
    }
    const saved = meta.browser?.config;
    if (meta.mode !== "browser" || saved?.manualLogin !== true ||
        saved.cookieSync !== false || saved.manualLoginCookieSync === true) {
      fail("saved session does not establish manual-login/no-cookie-sync operation.");
    }
    for (const candidate of [saved.manualLoginProfileDir,
      meta.browser?.runtime?.userDataDir, meta.browser?.runtime?.chromeProfileRoot]) {
      if (candidate != null && path.resolve(cwd, candidate) !== profile) {
        fail("saved session profile differs from --profile-dir.");
      }
    }
    if (!saved.manualLoginProfileDir && !meta.browser?.runtime?.userDataDir) {
      fail("saved session has no explicit profile evidence.");
    }
    const request = readOptional(path.join(dir, "request.json"));
    if (request !== undefined) {
      try { checkConfig(JSON.parse(request)); } catch { fail("saved request is invalid or contains cookie configuration."); }
    }
    oracleArgs = ["session", id, ...parseOptions(options, ["--write-output"],
      ["--harvest", "--live", "--no-recover", "--hide-prompt"])];
  } else {
    fail("choose preview, submit, status, or session; restart and follow-ups are unsupported.");
  }
  effectiveEnv.ORACLE_HOME_DIR = home;
  effectiveEnv.ORACLE_BROWSER_PROFILE_DIR = profile;
  effectiveEnv.DOTENV_CONFIG_PATH = "/dev/null";
  effectiveEnv.DOTENV_CONFIG_OVERRIDE = "false";
  effectiveEnv.DOTENV_CONFIG_DEBUG = "false";
  effectiveEnv.DOTENV_CONFIG_QUIET = "true";
  return { cli, args: oracleArgs, env: effectiveEnv };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === fs.realpathSync(process.argv[1])) {
  let invocation;
  try {
    if (Number(process.versions.node.split(".")[0]) < 24) fail("Node.js 24 or newer is required.");
    const args = process.argv.slice(2);
    if (args[0] !== "--oracle-cli" || args[2] !== "--oracle-home" || args[4] !== "--profile-dir") {
      fail("expected --oracle-cli PATH --oracle-home PATH --profile-dir PATH MODE [options].");
    }
    invocation = prepareInvocation({ cli: args[1], home: args[3], profile: args[5], args: args.slice(6) });
  } catch (error) {
    process.stderr.write((error.message?.startsWith("pro-review guard:")
      ? error.message : "pro-review guard: preflight failed; no transport action was started.") + "\n");
    process.exitCode = 2;
  }
  if (invocation) {
    for (const key of Object.keys(process.env)) delete process.env[key];
    Object.assign(process.env, invocation.env);
    process.argv = [process.execPath, invocation.cli, ...invocation.args];
    await import(pathToFileURL(invocation.cli).href);
  }
}
