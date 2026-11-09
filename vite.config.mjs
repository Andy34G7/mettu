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
import { processImages } from './src/image-preprocess.mjs';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const inputDir = path.join(__dirname, '/assets/images');
const outputDir = path.join(__dirname, '/assets/images-processed');
const siteConfigPath = path.join(__dirname, 'config.yaml');
const requirementsPath = path.join(__dirname, 'requirements.txt');

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
    ? [path.join(__dirname, '.venv/Scripts/python.exe'), path.join(__dirname, '.venv/bin/python')]
    : [path.join(__dirname, '.venv/bin/python'), path.join(__dirname, '.venv/Scripts/python.exe')];
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
  const venvPath = path.join(__dirname, '.venv');
  const isWindows = process.platform === 'win32';
  
  const venvPython = isWindows 
    ? path.join(venvPath, 'Scripts', 'python.exe')
    : path.join(venvPath, 'bin', 'python');

  const venvPip = isWindows
    ? path.join(venvPath, 'Scripts', 'pip.exe')
    : path.join(venvPath, 'bin', 'pip');

  const hashFile = path.join(__dirname, '.cache/requirements.hash');
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

const GLOB_IGNORES = ['!dist/**', '!node_modules/**', '!**/.venv/**', '!templates/**', '!public/**', '!content/**', '!assets/**', '!src/**', '!scripts/**', '!tests/**'];

const handleExit = () => {
  console.log('\nCleaning up build files...');
  try {
    const output = execFileSync(pythonExecutable, ['src/main.py', '--clean']);
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
      const xmlFiles = glob.sync(['**/*.xml', ...GLOB_IGNORES]);
      for (const relPath of xmlFiles) {
        const destPath = path.join('./dist', relPath);
        fs.mkdirSync(path.dirname(destPath), { recursive: true });
        fs.copyFileSync(relPath, destPath);
      }

      console.log('Cleaning up root directory...');
      try {
        const output = execFileSync(pythonExecutable, ['src/main.py', '--clean']);
        console.log(output.toString().trim());
      } catch (e) {
        console.error('Failed to cleanup:', e);
      }
    },
    configureServer(server) {
      const build = (file = null) => {
        try {
          const args = file ? ['src/main.py', '--file', file] : ['src/main.py'];
          const output = execFileSync(pythonExecutable, args);
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
    if (requiredCss.some(f => !fs.existsSync(path.join(__dirname, f)))) {
      try {
        execFileSync(pythonExecutable, ['src/main.py', '--generate-styles']);
      } catch (e) {
        console.error('[styles] failed to generate theme/font CSS.', e);
      }
    }
  }

  if (command === 'build') {
    console.log('Buiding static pages for production');
    try {
      const output = execFileSync(pythonExecutable, ['src/main.py']);
      console.log(output.toString().trim());
    } catch (e) {
      console.error('Failed to generate static files:', e);
      throw e;
    }
  }

  const inputFiles = glob.sync(['**/*.html', ...GLOB_IGNORES]);

  return {
    plugins: [
      py_build_plugin(),
      tailwindcss(),
    ],
    build: {
      outDir: './dist',
      rollupOptions: {
        input: inputFiles,
      },
    },
    server: {
      watch: {
        ignored: (p) => {
          const relPath = path.relative(__dirname, p).replace(/\\/g, '/');
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
