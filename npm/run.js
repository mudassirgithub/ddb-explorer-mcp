#!/usr/bin/env node
//
// Thin npm shim for ddb-explorer-mcp.
//
// Spawns the real Python-based MCP server via `uvx` (or `uv tool run`).
// JS-ecosystem users can install and run the server with:
//
//   npx ddb-explorer-mcp
//
// Requirements: uv must be installed (https://github.com/astral-sh/uv).
// If uv is not found, the script prints a helpful message and exits.

"use strict";

const { execFileSync, spawn } = require("child_process");
const os = require("os");

function commandExists(cmd) {
  try {
    // cross-platform: `where` on Windows, `command -v` via shell elsewhere
    if (os.platform() === "win32") {
      execFileSync("where", [cmd], { stdio: "ignore" });
    } else {
      execFileSync("command", ["-v", cmd], { stdio: "ignore", shell: true });
    }
    return true;
  } catch {
    return false;
  }
}

function resolveCommand() {
  if (commandExists("uvx")) return { cmd: "uvx", args: ["ddb-explorer-mcp"] };
  if (commandExists("uv")) return { cmd: "uv", args: ["tool", "run", "ddb-explorer-mcp"] };
  return null;
}

const resolved = resolveCommand();

if (!resolved) {
  const isWin = os.platform() === "win32";
  process.stderr.write(
    "\n" +
      "ERROR: ddb-explorer-mcp requires `uv` (the Python package manager).\n" +
      "\n" +
      "Install it with:\n" +
      (isWin
        ? "  powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"\n"
        : "  curl -LsSf https://astral.sh/uv/install.sh | sh\n") +
      "\n" +
      "Or via Homebrew:\n" +
      "  brew install uv\n" +
      "\n" +
      "Then retry:  npx ddb-explorer-mcp\n" +
      "\n"
  );
  process.exit(1);
}

const child = spawn(resolved.cmd, [...resolved.args, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code) => process.exit(code ?? 1));
child.on("error", (err) => {
  process.stderr.write(`Failed to start ${resolved.cmd}: ${err.message}\n`);
  process.exit(1);
});
