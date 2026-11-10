import sharp from 'sharp';
import fs from 'fs/promises';
import fsSync from 'fs';
import path from 'path';
import { S3Client, PutObjectCommand, HeadObjectCommand } from '@aws-sdk/client-s3';
import { NodeHttpHandler } from "@smithy/node-http-handler";
import * as https from "https";


const TARGET_WIDTHS = [640, 1280];

// Default to WebP if no configuration is provided
const DEFAULT_FORMATS = ['webp'];

const FORMAT_HANDLERS = {
    webp: img => img.webp({ quality: 80 }),
    avif: img => img.avif({ quality: 50 }),
    jpg: img => img.jpeg({ quality: 80, mozjpeg: true, progressive: true }),
    jpeg: img => img.jpeg({ quality: 80, mozjpeg: true, progressive: true }),
    png: img => img.png({ quality: 80 }),
};

function getS3Client() {
    if (!process.env.S3_BUCKET || !process.env.S3_ACCESS_KEY || !process.env.S3_SECRET_KEY) {
        return null;
    }
    const clientConfig = {
        region: process.env.S3_REGION || 'auto',
        endpoint: process.env.S3_ENDPOINT || undefined,
        credentials: {
            accessKeyId: process.env.S3_ACCESS_KEY,
            secretAccessKey: process.env.S3_SECRET_KEY,
        },
        forcePathStyle: true // Needed for some S3-compatible providers like MinIO
    };

    if (process.env.S3_INSECURE_TLS === 'true') {
        clientConfig.requestHandler = new NodeHttpHandler({
            httpsAgent: new https.Agent({ rejectUnauthorized: false })
        });
    }

    return new S3Client(clientConfig);
}

export async function processImages(inputDir, outputDir, siteConfig = {}) {
    await fs.mkdir(outputDir, { recursive: true });
    
    // Determine configured formats
    let configuredStats = siteConfig.images && siteConfig.images.formats;
    if (!configuredStats || !Array.isArray(configuredStats) || configuredStats.length === 0) {
        configuredStats = DEFAULT_FORMATS;
    }
    const targetFormats = configuredStats.filter(f => FORMAT_HANDLERS[f]);

    const s3 = getS3Client();
    const bucket = process.env.S3_BUCKET;

    const allEntries = await fs.readdir(inputDir, { recursive: true });
    const files = allEntries.filter(f => /\.(png|jpe?g|gif)$/i.test(f));

    // { originalFile: { format: [{ width, path }] } }
    const manifest = {};
    const metaCachePath = '.cache/image-meta.json';
    let metaCache = {};
    if (fsSync.existsSync(metaCachePath)) {
        try {
            metaCache = JSON.parse(fsSync.readFileSync(metaCachePath, 'utf8'));
        } catch (_) {}
    }
    const nextMetaCache = {};

    for (const file of files) {
        const inputPath = path.join(inputDir, file);
        const manifestKey = file.split(path.sep).join('/');
        let origWidth;
        let isCacheHit = false;

        try {
            const stat = await fs.stat(inputPath);
            if (!stat.isFile()) continue;

            const cached = metaCache[manifestKey];
            if (cached && cached.mtimeMs === stat.mtimeMs && cached.size === stat.size && cached.width) {
                origWidth = cached.width;
                isCacheHit = true;
                nextMetaCache[manifestKey] = cached;
            } else {
                const meta = await sharp(inputPath).metadata();
                origWidth = meta.width || Math.max(...TARGET_WIDTHS);
                nextMetaCache[manifestKey] = {
                    mtimeMs: stat.mtimeMs,
                    size: stat.size,
                    width: origWidth,
                };
            }
        } catch (e) {
            console.error(`[img] metadata fail ${file}: ${e.message}`);
            continue;
        }

        const widths = [...new Set(
            TARGET_WIDTHS.filter(w => w <= origWidth).concat([origWidth])
        )].sort((a, b) => a - b);

        const baseName = manifestKey.replace(/\.(png|jpe?g|gif)$/i, '');

        // Ensure entry exists
        manifest[manifestKey] ||= {};

        for (const w of widths) {
            for (const ext of targetFormats) {
                const handler = FORMAT_HANDLERS[ext];
                const outFile = `${baseName}-${w}.${ext}`;
                const outPath = path.join(outputDir, outFile);
                
                // Ensure output subdirectory exists
                await fs.mkdir(path.dirname(outPath), { recursive: true });

                const key = `assets/images/${outFile}`;
                
                let publicUrl;
                let s3ObjectExists = false;

                if (s3) {
                     // Check if object exists in S3 to avoid re-uploading
                     try {
                         await s3.send(new HeadObjectCommand({ Bucket: bucket, Key: key }));
                         s3ObjectExists = true;
                     } catch (e) {
                         if (e.name !== 'NotFound' && e.$metadata?.httpStatusCode !== 404) {
                             console.warn(`[img] error checking ${key}: ${e.message}`);
                         }
                         // If 404, s3ObjectExists remains false
                     }
                }

                try {
                    // Always regenerate local file to ensure it exists for upload
                    if (!isCacheHit || !fsSync.existsSync(outPath)) {
                         await handler(sharp(inputPath).resize({ width: w })).toFile(outPath);
                         console.log(`[img] processed local ${file} -> ${outFile}`);
                    }

                    if (s3) {
                         // Construct URL first
                         if (process.env.S3_PUBLIC_URL) {
                              publicUrl = `${process.env.S3_PUBLIC_URL.replace(/\/$/, '')}/${key}`;
                         } else {
                              const rawEndpoint = process.env.S3_ENDPOINT || `https://s3.${process.env.S3_REGION || 'us-east-1'}.amazonaws.com`;
                              const endpoint = rawEndpoint.replace(/\/$/, '');
                              publicUrl = `${endpoint}/${bucket}/${key}`;
                         }

                         if (!s3ObjectExists) {
                             const fileBuffer = await fs.readFile(outPath);
                             const contentType = ext === 'jpg' ? 'image/jpeg' : `image/${ext}`;
                             
                             console.log(`[img] uploading ${outFile} to S3...`);
                             await s3.send(new PutObjectCommand({
                                 Bucket: bucket,
                                 Key: key,
                                 Body: fileBuffer,
                                 ContentType: contentType,
                                 // ACL removed
                             }));
                         }
                    } else {
                         // Local path
                         publicUrl = path.posix.join(
                             path.relative(process.cwd(), outputDir).split(path.sep).join('/'),
                             outFile
                         );
                    }

                    (manifest[manifestKey][ext] ||= []).push({ width: w, path: publicUrl });

                } catch (e) {
                    console.error(`[img] fail ${file} (${w}px ${ext}): ${e.message}`);
                }
            }
        }
    }

    fsSync.mkdirSync('.cache', { recursive: true });
    fsSync.writeFileSync(metaCachePath, JSON.stringify(nextMetaCache, null, 2));
    fsSync.writeFileSync('.cache/image-manifest.json', JSON.stringify(manifest, null, 2));
    return manifest;
}
