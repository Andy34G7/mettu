<?xml version="1.0" encoding="utf-8"?>
<!--
  pretty-feed-v3.xsl - A simple XSL stylesheet to render Atom/RSS feeds
  as a human-readable HTML page in a browser.

  Source: https://github.com/genmon/aboutfeeds
  License: MIT
-->
<xsl:stylesheet
  version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom"
  xmlns:dc="http://purl.org/dc/elements/1.1/"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html xmlns="http://www.w3.org/1999/xhtml" lang="en">
      <head>
        <title><xsl:value-of select="/atom:feed/atom:title"/> - Web Feed</title>
        <meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1"/>
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Red+Hat+Display:wght@400;600;700&amp;family=Red+Hat+Text:wght@400;500&amp;display=swap');

          /* ── retro-dark ── */
          :root {
            --base-100: #1A1D1E;
            --base-200: #24282A;
            --base-300: #2F3538;
            --base-content: #E8EAEA;
            --primary: #A5C9CA;
            --secondary: #8CA3A6;
            --shadow: rgba(0,0,0,.4);
          }

          /* ── Layout ── */
          *{box-sizing:border-box}
          body{font-family:'Red Hat Text',system-ui,sans-serif;margin:0;padding:0;background:var(--base-100);color:var(--base-content)}

          /* ── Hero ── */
          .hero{background:var(--base-200);border-bottom:1px solid var(--base-300);padding:3rem 1.5rem 2.5rem;position:relative}
          .hero-container{max-width:860px;margin:0 auto;display:flex;align-items:center;gap:2rem}
          .hero-logo-box{flex-shrink:0;width:72px;height:72px;border-radius:1.25rem;background:var(--primary);display:flex;align-items:center;justify-content:center;transition:transform .2s ease;cursor:default}
          .hero-logo-box:hover{transform:scale(1.05)}
          .hero-logo-box svg{width:36px;height:36px;fill:var(--base-100);transition:transform .2s ease}
          .hero-logo-box:hover svg{transform:rotate(5deg)}
          .hero-content{flex-grow:1}
          .hero h1{margin:0 0 .5rem;font-family:'Red Hat Display',sans-serif;font-size:2rem;font-weight:700;color:var(--primary)}
          .hero p{margin:0;opacity:.8;max-width:60ch}
          .hero a{color:var(--primary);text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--primary) 40%,transparent)}
          .hero a:hover{opacity:1;border-bottom-color:var(--primary)}

          /* ── Badge ── */
          .badge{display:inline-flex;align-items:center;gap:.4rem;background:color-mix(in srgb,var(--primary) 12%,transparent);border:1px solid color-mix(in srgb,var(--primary) 30%,transparent);border-radius:999px;padding:.25rem .75rem;font-size:.8rem;color:var(--primary);margin-bottom:1.25rem}
          .badge svg{width:14px;height:14px;fill:currentColor}

          /* ── Container ── */
          .container{max-width:860px;margin:0 auto;padding:2rem 1.5rem}

          /* ── About box ── */
          .about{background:var(--base-200);border:1px solid var(--base-300);border-radius:1rem;padding:1.25rem 1.5rem;margin-bottom:2rem;font-size:.9rem;color:var(--secondary);line-height:1.6}
          .about strong{color:var(--base-content)}
          .about a{color:var(--primary);text-decoration:underline;text-underline-offset:3px}

          /* ── Section heading ── */
          h2{font-family:'Red Hat Display',sans-serif;font-size:.85rem;font-weight:600;color:var(--secondary);margin:0 0 1.25rem;padding-bottom:.5rem;border-bottom:1px solid var(--base-300);text-transform:uppercase;letter-spacing:.08em}

          /* ── Entry cards ── */
          .entry{background:var(--base-200);border:1px solid var(--base-300);border-radius:1rem;padding:1.25rem 1.5rem;margin-bottom:.75rem;transition:box-shadow .2s,border-color .2s}
          .entry:hover{box-shadow:0 4px 16px var(--shadow);border-color:var(--primary)}
          .entry h3{margin:0 0 .35rem;font-family:'Red Hat Display',sans-serif;font-size:1.05rem}
          .entry h3 a{color:var(--base-content);text-decoration:none}
          .entry h3 a:hover{color:var(--primary)}
          .meta{font-size:.8rem;color:var(--primary);display:flex;gap:.75rem;flex-wrap:wrap;margin-bottom:.4rem;align-items:center}
          .meta time{display:flex;align-items:center;gap:.3rem}
          .summary{font-size:.875rem;color:var(--secondary);line-height:1.55;margin:.4rem 0 0}
          .tag{background:color-mix(in srgb,var(--primary) 10%,transparent);color:var(--primary);border:1px solid color-mix(in srgb,var(--primary) 25%,transparent);border-radius:999px;padding:.15rem .6rem;font-size:.75rem;font-weight:500}

          @media(max-width:600px){
            .hero{padding:2rem 1rem 2rem}
            .hero h1{font-size:1.5rem}
            .container{padding:1.5rem 1rem}
            .hero-container{flex-direction:column;align-items:flex-start;gap:1.25rem}
            .hero-logo-box{width:56px;height:56px;border-radius:1rem}
            .hero-logo-box svg{width:28px;height:28px}
          }
        </style>
      </head>
      <body>
        <div class="hero">
          <div class="hero-container">
            <div class="hero-logo-box">
              <svg viewBox="0 0 24 24"><path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19.01 7.38 20 6.18 20 4.98 20 4 19.01 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/></svg>
            </div>
            <div class="hero-content">
              <div class="badge">
                <svg viewBox="0 0 24 24"><path d="M6.18 15.64a2.18 2.18 0 0 1 2.18 2.18C8.36 19.01 7.38 20 6.18 20 4.98 20 4 19.01 4 17.82a2.18 2.18 0 0 1 2.18-2.18M4 4.44A15.56 15.56 0 0 1 19.56 20h-2.83A12.73 12.73 0 0 0 4 7.27V4.44m0 5.66a9.9 9.9 0 0 1 9.9 9.9h-2.83A7.07 7.07 0 0 0 4 12.93V10.1z"/></svg>
                Web Feed
              </div>
              <h1><xsl:value-of select="/atom:feed/atom:title"/></h1>
              <p><xsl:value-of select="/atom:feed/atom:subtitle"/>
                <xsl:if test="/atom:feed/atom:link[@rel='alternate']/@href">
                  - <a><xsl:attribute name="href"><xsl:value-of select="/atom:feed/atom:link[@rel='alternate']/@href"/></xsl:attribute>Visit site →</a>
                </xsl:if>
              </p>
            </div>
          </div>
        </div>

        <div class="container">
          <div class="about">
            <strong>This is a web feed.</strong> Subscribe by copying the URL from the address bar into your feed reader.
            <br/>New to feeds? <a href="https://aboutfeeds.com" target="_blank">Learn about feeds →</a>
          </div>
          <h2>Recent posts</h2>
          <xsl:apply-templates select="/atom:feed/atom:entry"/>
        </div>
      </body>
    </html>
  </xsl:template>

  <xsl:template match="atom:entry">
    <div class="entry">
      <h3>
        <a>
          <xsl:attribute name="href"><xsl:value-of select="atom:link/@href"/></xsl:attribute>
          <xsl:value-of select="atom:title"/>
        </a>
      </h3>
      <div class="meta">
        <time>
          <xsl:attribute name="datetime"><xsl:value-of select="atom:published"/></xsl:attribute>
          <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          <xsl:value-of select="substring(atom:published, 1, 10)"/>
        </time>
        <xsl:for-each select="atom:category">
          <span class="tag"><xsl:value-of select="@term"/></span>
        </xsl:for-each>
      </div>
      <xsl:if test="atom:summary">
        <p class="summary"><xsl:value-of select="atom:summary"/></p>
      </xsl:if>
    </div>
  </xsl:template>
</xsl:stylesheet>
