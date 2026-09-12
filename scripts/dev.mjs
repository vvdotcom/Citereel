import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { randomBytes } from "node:crypto";
import path from "node:path";

const root = process.cwd();
const python = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
if (!existsSync(python)) {
  console.error("Run npm run setup first.");
  process.exit(1);
}
const env = {
  ...process.env,
  LAUNCHPAD_API_SECRET:
    process.env.LAUNCHPAD_API_SECRET || randomBytes(32).toString("hex"),
  LAUNCHPAD_REQUIRE_PROXY_SECRET: process.env.LAUNCHPAD_REQUIRE_PROXY_SECRET || "false",
  PYTHONPATH: ["services/api/src", "services/agent/src", "services/worker/src"]
    .map((x) => path.join(root, x))
    .join(path.delimiter),
  PYTHONUNBUFFERED: "1",
};
const children = [];
function start(command, args) {
  const child = spawn(command, args, {
    cwd: root,
    env,
    stdio: "inherit",
    windowsHide: true,
  });
  children.push(child);
  child.on("exit", (code) => {
    if (code) {
      console.error("A Launchpad service exited:", code);
      shutdown();
    }
  });
  return child;
}
function shutdown() {
  for (const child of children) child.kill();
  process.exit();
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
start(python, [
  "-m",
  "uvicorn",
  "launchpad_api.main:app",
  "--host",
  "127.0.0.1",
  "--port",
  "8011",
]);
start(python, ["-m", "launchpad_worker.runner"]);
start(process.execPath, [
  "node_modules/next/dist/bin/next",
  process.argv.includes("--production") ? "start" : "dev",
  "--hostname",
  process.env.LAUNCHPAD_WEB_HOST || "127.0.0.1",
  "--port",
  process.env.LAUNCHPAD_WEB_PORT || "3011",
]);
