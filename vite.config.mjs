import { defineConfig } from "vite";
import dotenv from 'dotenv';
import tailwindcss from "@tailwindcss/vite";
import { execSync } from 'child_process';
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

const getScriptPath = (scriptName) => {
  const isWindows = process.platform === 'win32';
  const name = isWindows ? `${scriptName}.bat` : `${scriptName}.sh`;
  return path.join(__dirname, 'scripts', name);
};

const runScript = (scriptName, args = '') => {
    const scriptPath = getScriptPath(scriptName);
    try {
        const cmd = args ? `"${scriptPath}" ${args}` : `"${scriptPath}"`;
        // console.log(`[scripts] Running: ${cmd}`);
        const output = execSync(cmd);
        const text = output.toString().trim();
        if (text) console.log(text);
        return text;
    } catch (e) {
        console.error(`[scripts] Failed to run ${scriptName}:`, e);
        throw e;
    }
};

const ensurePythonRequirements = () => {
    try {
        const setupScript = getScriptPath('setup_env');
        console.log(`[setup] Running: ${setupScript}`);
        execSync(`"${setupScript}"`, { stdio: 'inherit' });
    } catch (e) {
        console.error('[setup] Failed.', e);
    }
};

const runGenerateStyles = () => {
    try {
        runScript('generate_styles');
    } catch (e) {
        console.error('[styles] Failed to regenerate styles.', e);
    }
};

ensurePythonRequirements();
runGenerateStyles();

const handleExit = () => {
  console.log('\nCleaning up build files...');
  try {
      runScript('clean');
  } catch (e) {
    console.error("Cleanup script failed:", e);
  }
  process.exit();
};

if (!process.listenerCount('SIGINT')) {
  process.on('SIGINT', handleExit);
}

const py_build_plugin = () => {
  let ready = false;

  return {
    name: 'builder-ssg',
    closeBundle() {
      console.log('Cleaning up root directory...');
      try {
          runScript('clean');
      } catch (e) {
        console.error('Failed to cleanup:', e);
      }
    },
    configureServer(server) {
      const regenerateGeneratedCss = () => {
        runGenerateStyles();
      };

      const build = (file = null) => {
        try {
            if (file) {
                 runScript('build', `--file "${file}"`);
            } else {
                 runScript('build');
            }

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
          regenerateGeneratedCss();
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
        }
        if (event === 'change' && filePath.includes('/assets/css/')) {
          build();
        }
        if (event === 'unlink') {
          if (!filePath.includes('/assets/images/')) {
              build();
          }
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

  if (command === 'build') {
    console.log('Buiding static pages for production');
    try {
        runScript('build');
    } catch (e) {
      console.error('Failed to generate static files:', e);
      throw e;
    }
  }

  const inputFiles = glob.sync(['**/*.html', '!dist/**', '!node_modules/**', '!**/.venv/**', '!templates/**']);

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
        ignored: [
          '**/assets/css/generated.daisyui.css',
          '**/assets/css/generated.fonts.css',
          '**/assets/css/syntax.css',
          '**/.venv/**',
          '**/dist/**',
          '**/index.html',
          '**/sitemap.xml',
          '**/blog/**',
          '**/posts/**',
          '**/tags/**'
        ]
      }
    }
  };
});
