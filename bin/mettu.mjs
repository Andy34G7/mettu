#!/usr/bin/env node
import { spawnSync } from 'child_process';
import fs from 'fs';
import { createRequire } from 'module';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const engineDir = path.resolve(path.dirname(__filename), '..');
const siteRoot = process.cwd();
const require = createRequire(import.meta.url);

const [, , rawCmd, ...restArgs] = process.argv;
const command = rawCmd || 'dev';

if (command === '-h' || command === '--help' || command === 'help') {
  console.log(`Usage: mettu <command> [options]

Commands:
  dev       Start the Vite development server
  build     Build the static site for production
  preview   Preview the production build
  new       Scaffold a new markdown file
  check     Validate site configuration and content
  clean     Remove generated build files from the site root`);
  process.exit(0);
}

const sharedEnv = {
  ...process.env,
  METTU_SITE_ROOT: siteRoot,
  METTU_ENGINE_DIR: engineDir,
};

const resolvePython = () => {
  if (process.env.PY_EXECUTABLE && process.env.PY_EXECUTABLE.trim()) {
    return process.env.PY_EXECUTABLE.trim();
  }
  const candidates = process.platform === 'win32'
    ? [path.join(siteRoot, '.venv/Scripts/python.exe'), path.join(siteRoot, '.venv/bin/python')]
    : [path.join(siteRoot, '.venv/bin/python'), path.join(siteRoot, '.venv/Scripts/python.exe')];
  return candidates.find((p) => fs.existsSync(p)) || (process.platform === 'win32' ? 'python' : 'python3');
};

if (command === 'dev' || command === 'build' || command === 'preview') {
  const vitePkgDir = path.dirname(require.resolve('vite/package.json'));
  const viteBin = path.join(vitePkgDir, 'bin', 'vite.js');
  const viteArgs = [viteBin];
  if (command !== 'dev') {
    viteArgs.push(command);
  }
  viteArgs.push('--config', path.join(engineDir, 'vite.config.mjs'), ...restArgs);

  const result = spawnSync(process.execPath, viteArgs, {
    cwd: siteRoot,
    env: sharedEnv,
    stdio: 'inherit',
  });
  process.exit(result.status ?? 1);
}

if (command === 'new' || command === 'check' || command === 'clean') {
  const pythonExec = resolvePython();
  const mainPy = path.join(engineDir, 'src/main.py');
  const result = spawnSync(pythonExec, [mainPy, `--${command}`, ...restArgs], {
    cwd: siteRoot,
    env: sharedEnv,
    stdio: 'inherit',
  });
  process.exit(result.status ?? 1);
}

console.error(`Unknown command: ${command}. Run "mettu --help" for usage.`);
process.exit(1);
