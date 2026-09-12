import { spawnSync } from "node:child_process";
const windows = process.platform === "win32";
function run(command, args) {
  const r = spawnSync(command, args, { stdio: "inherit", windowsHide: true });
  if (r.status !== 0) process.exit(r.status || 1);
}
run(windows ? "python" : "python3", ["-m", "venv", ".venv"]);
const python = windows ? ".venv/Scripts/python.exe" : ".venv/bin/python";
run(python, ["-m", "pip", "install", "-r", "requirements.txt"]);
run(python, ["-m", "playwright", "install", "chromium"]);
