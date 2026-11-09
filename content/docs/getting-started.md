---
title: "Getting Started"
section: "Guide"
order: 2
---

Getting started with `mettu` takes only a few minutes.

## Prerequisites

- **Node.js**: v18+ and `npm`
- **Python**: 3.10+ with standard library and virtual environment support

## Quick Installation

Clone your repository and install dependencies:

```bash
git clone https://github.com/yourusername/my-site.git
cd my-site
npm install
```

## Running the Dev Server

Start the interactive development server:

```bash
npm run dev
```

The Vite dev server will watch markdown files, templates, styles, and images, automatically triggering fast incremental rebuilds.

## Production Build

To build your production static site:

```bash
npm run build
```

Generated assets will be written to the `dist/` directory, ready to deploy to GitHub Pages, Cloudflare Pages, Vercel, or Netlify.
