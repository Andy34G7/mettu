import { defineConfig } from "vite";
import dotenv from 'dotenv';
import tailwindcss from "@tailwindcss/vite";
import { execFileSync } from 'child_process';
import crypto from 'crypto';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import YAML from 'yaml';
import glob from 'fast-glob';
import { createRequire } from 'module';
import { processImages } from './src/image-preprocess.mjs';

const require = createRequire(import.meta.url);

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const engineDir = path.dirname(__filename);
const siteRoot = path.resolve(process.env.METTU_SITE_ROOT || process.cwd());

const inputDir = path.join(siteRoot, 'assets/images');
const outputDir = path.join(siteRoot, 'assets/images-processed');
const siteConfigPath = path.join(siteRoot, 'config.yaml');
const requirementsPath = path.join(engineDir, 'requirements.txt');
const mainPyPath = path.join(engineDir, 'src/main.py');

const runPythonScript = (args = []) => {
  return execFileSync(pythonExecutable, [mainPyPath, ...args], {
    cwd: siteRoot,
    env: { ...process.env, METTU_ENGINE_DIR: engineDir },
  });
};

const loadSiteConfig = () => {
  try {
    const raw = fs.readFileSync(siteConfigPath, 'utf8');
    return YAML.parse(raw) || {};
  } catch (err) {
    console.error('[config] Unable to read config.yaml', err);
    return {};
  }
};


if (!fs.existsSync(inputDir)) {
  fs.mkdirSync(inputDir, { recursive: true });
}

const sanitizeExecutable = (value) => {
  if (typeof value !== 'string') {
    return '';
  }
  return value.trim();
};

const resolvePythonExecutable = () => {
  const envOverride = sanitizeExecutable(process.env.PY_EXECUTABLE);
  if (envOverride) {
    return envOverride;
  }

  const venvCandidates = process.platform === 'win32'
    ? [path.join(siteRoot, '.venv/Scripts/python.exe'), path.join(siteRoot, '.venv/bin/python')]
    : [path.join(siteRoot, '.venv/bin/python'), path.join(siteRoot, '.venv/Scripts/python.exe')];
  const foundVenv = venvCandidates.find(p => fs.existsSync(p));
  if (foundVenv) return foundVenv;

  const siteConfig = loadSiteConfig();
  const runtimeConfig = siteConfig && typeof siteConfig === 'object' ? siteConfig.runtime : null;

  const candidates = [
    runtimeConfig && runtimeConfig.python_executable,
    runtimeConfig && runtimeConfig.python,
    runtimeConfig && runtimeConfig.interpreter,
    siteConfig && siteConfig.python_executable,
    siteConfig && siteConfig.python,
  ];

  for (const candidate of candidates) {
    const value = sanitizeExecutable(candidate);
    if (value) {
      return value;
    }
  }

  return process.platform === 'win32' ? 'python' : 'python3';
};

let pythonExecutable = resolvePythonExecutable();
console.log(`[config] Using Python executable: ${pythonExecutable}`);

const ensurePythonRequirements = () => {
  const venvPath = path.join(siteRoot, '.venv');
  const isWindows = process.platform === 'win32';
  
  const venvPython = isWindows 
    ? path.join(venvPath, 'Scripts', 'python.exe')
    : path.join(venvPath, 'bin', 'python');

  const venvPip = isWindows
    ? path.join(venvPath, 'Scripts', 'pip.exe')
    : path.join(venvPath, 'bin', 'pip');

  const hashFile = path.join(siteRoot, '.cache/requirements.hash');
  let currentHash = '';
  try {
    const content = fs.readFileSync(requirementsPath, 'utf8') + '\n' + venvPython + '\n' + pythonExecutable;
    currentHash = crypto.createHash('sha256').update(content).digest('hex');
  } catch (e) {
    console.error('Failed to read requirements.txt:', e);
  }

  if (fs.existsSync(venvPython) && fs.existsSync(hashFile)) {
    try {
      const cachedHash = fs.readFileSync(hashFile, 'utf8').trim();
      if (cachedHash === currentHash && currentHash) {
        return;
      }
    } catch (_) {}
  }

  if (!fs.existsSync(venvPython)) {
    console.log('Creating python virtual environment...');
    try {
      execFileSync(pythonExecutable, ['-m', 'venv', venvPath], { stdio: 'inherit' });
      pythonExecutable = venvPython;
    } catch (e) {
      console.error('Failed to create virtual environment.', e);
      return;
    }
  }

  try {
    console.log('Installing python dependencies...');
    execFileSync(venvPip, ['install', '-r', requirementsPath], { stdio: 'inherit' });
    if (currentHash) {
      fs.mkdirSync(path.dirname(hashFile), { recursive: true });
      fs.writeFileSync(hashFile, currentHash, 'utf8');
    }
  } catch (e) {
    console.error('Failed to install Python dependencies.', e);
  }
};

const refreshPythonExecutable = () => {
  const resolved = resolvePythonExecutable();
  if (resolved !== pythonExecutable) {
    console.log(`[config] Python executable updated to: ${resolved}`);
    pythonExecutable = resolved;
    ensurePythonRequirements();
  }
  return pythonExecutable;
};

ensurePythonRequirements();

const GLOB_IGNORES = ['!dist/**', '!node_modules/**', '!**/.venv/**', '!templates/**', '!public/**', '!content/**', '!assets/**', '!bin/**', '!src/**', '!scripts/**', '!tests/**'];

const handleExit = () => {
  console.log('\nCleaning up build files...');
  try {
    const output = runPythonScript(['--clean']);
    console.log(output.toString().trim());
  } catch (e) {
    console.error("Cleanup script failed:", e);
  }
  process.exit();
};

// Ensure we only attach the listener once
if (!process.listenerCount('SIGINT')) {
  process.on('SIGINT', handleExit);
}

const py_build_plugin = () => {
  let ready = false;

  return {
    name: 'builder-ssg',
    closeBundle() {
      const distDir = path.join(siteRoot, 'dist');
      const xmlFiles = glob.sync(['**/*.xml', ...GLOB_IGNORES], { cwd: siteRoot });
      for (const relPath of xmlFiles) {
        const destPath = path.join(distDir, relPath);
        fs.mkdirSync(path.dirname(destPath), { recursive: true });
        fs.copyFileSync(path.join(siteRoot, relPath), destPath);
      }

      const searchIndex = path.join(siteRoot, 'search-index.json');
      if (fs.existsSync(searchIndex)) {
        fs.copyFileSync(searchIndex, path.join(distDir, 'search-index.json'));
      }

      console.log('Cleaning up root directory...');
      try {
        const output = runPythonScript(['--clean']);
        console.log(output.toString().trim());
      } catch (e) {
        console.error('Failed to cleanup:', e);
      }
    },
    configureServer(server) {
      const build = (file = null) => {
        try {
          const args = file ? ['--file', file] : [];
          const output = runPythonScript(args);
          console.log(output.toString().trim());

          server.ws.send({ type: 'full-reload', path: "*" });
          ready = true;
        } catch (e) {
          console.error("Script failed to update: ", e);
        }
      };

      build();

      server.watcher.on('all', async (event, filePath) => {
        if (!ready) {
          return;
        }

        if (filePath.endsWith('config.yaml')) {
          refreshPythonExecutable();
          build();
          return;
        }

        if (filePath.includes('/content/') || filePath.includes('/templates/')) {
          if (event === 'change') {
            const buildTarget = filePath.includes('/templates/') ? null : filePath;
            build(buildTarget);
          } else if (event === 'add' || event === 'unlink') {
            build();
          }
          return;
        }
        if (filePath.includes('/assets/images/')) {
          if (event === 'add' || event === 'change' || event === 'unlink') {
            console.log(`[watcher] Image change detected: ${event} ${filePath}`);
            try {
              const siteConfig = loadSiteConfig();
              await processImages(inputDir, outputDir, siteConfig);
              build();
            } catch (e) {
              console.error('[watcher] Image processing failed', e);
            }
          }
          return;
        }
        if (event === 'change' && filePath.includes('/assets/css/')) {
          build();
          return;
        }
        if (event === 'unlink') {
          if (!filePath.includes('/assets/images/')) {
            build();
          }
          return;
        }
      });
    },
  };
};

export default defineConfig(async ({ command }) => {
  try {
    const siteConfig = loadSiteConfig();
    await processImages(inputDir, outputDir, siteConfig);
  } catch (e) {
    console.error('[images] processing failed', e);
  }

  if (command !== 'build') {
    const requiredCss = [
      'assets/css/generated.daisyui.css',
      'assets/css/generated.fonts.css',
      'assets/css/syntax.css'
    ];
    if (requiredCss.some(f => !fs.existsSync(path.join(siteRoot, f)))) {
      try {
        runPythonScript(['--generate-styles']);
      } catch (e) {
        console.error('[styles] failed to generate theme/font CSS.', e);
      }
    }
  }

  if (command === 'build') {
    console.log('Buiding static pages for production');
    try {
      const output = runPythonScript([]);
      console.log(output.toString().trim());
    } catch (e) {
      console.error('Failed to generate static files:', e);
      throw e;
    }
  }

  const inputFiles = glob
    .sync(['**/*.html', ...GLOB_IGNORES], { cwd: siteRoot })
    .map(relPath => path.join(siteRoot, relPath));

  return {
    root: siteRoot,
    resolve: {
      alias: {
        tailwindcss: path.join(path.dirname(require.resolve('tailwindcss/package.json')), 'index.css'),
        '@tailwindcss/typography': require.resolve('@tailwindcss/typography'),
        daisyui: path.dirname(require.resolve('daisyui/package.json')),
      },
    },
    plugins: [
      py_build_plugin(),
      tailwindcss(),
    ],
    build: {
      outDir: path.join(siteRoot, 'dist'),
      rollupOptions: {
        input: inputFiles,
      },
    },
    server: {
      watch: {
        ignored: (p) => {
          const relPath = path.relative(siteRoot, p).replace(/\\/g, '/');
          if (!relPath || relPath === '.') return false;
          if (relPath.startsWith('..')) return true;

          const whitelisted = ['templates', 'content', 'assets', 'config.yaml', 'vite.config.mjs'];
          const isWhitelisted = whitelisted.some(base => relPath === base || relPath.startsWith(base + '/'));
          
          if (isWhitelisted) {
            const isGeneratedCss = [
              'assets/css/generated.daisyui.css',
              'assets/css/generated.fonts.css',
              'assets/css/syntax.css'
            ].some(gen => relPath === gen);
            
            return isGeneratedCss;
          }
          
          return true;
        }
      }
    }
  };
});
