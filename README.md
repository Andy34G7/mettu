# mettu - a Static Site Generator using Python and Vite

mettu (మెట్లు, /ˈmɛt.t̪u/) is a simple static site generator that uses Python for backend processing and Vite for frontend development, with Tailwind and DaisyUI for styling. It allows you to create static websites using markdown files.

## Why the name?
"mettu" is a Telugu word meaning a stair or step. It felt like a great name given that this project is a step towards building tools myself, and convieniently, a step towards making a site!

## Requirements
- Python 3.x
- Node.js and npm
- Vite
- Tailwind CSS and DaisyUI

## Setup
1. Clone the repository
2. Install the required dependencies

   ```bash
   npm install
   ```

   - Note: Python dependencies are installed by default by the initialising script.

3. Configure Environment Variables (Optional - for S3 Upload)

   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` to add your S3 bucket credentials. This is required if you want optimized images to be uploaded to an S3-compatible bucket.

4. Edit the `config.yaml` file to set your site name, author, runtime configuration, navigation links, syntax highlighting theme, and DaisyUI theme preferences.

   ```yaml
   runtime:
      python_executable: "python3"    # optional, defaults to python3 when omitted
   theme:
     default: "cupcake"                # active theme used for data-theme
     include: ["cupcake", "dracula"]  # DaisyUI presets to load
     custom:
       mytheme:
         primary: "#570df8"
         secondary: "#f000b8"
         accent: "#37cdbe"
   
   images:
     formats:
       - webp
       - jpg
   ```

    Optionally, define site-wide font imports and the families to apply:

    ```yaml
    fonts:
       imports:
          - "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@500;700&display=swap"
       families:
          body: "'Inter', sans-serif"
          heading: "'Space Grotesk', sans-serif"
          mono: "'JetBrains Mono', monospace"

    syntax:
       pygments_theme: "dracula"   # Controls syntax.css and markdown highlighting
    ```

   You can still override the interpreter via the `PY_EXECUTABLE` environment variable if needed, but the config file is the canonical source.

5. Create markdown files in the `content` directory.
   - **Dynamic Routing**: Nested directories are supported (e.g., `content/blog/post-1.md` becomes `/blog/post-1.html`).
   - Each file should start with frontmatter similarly to the given examples.

6. Templates and svg icons are located in the `templates` directory. You can customize them as needed.

7. Assets like css, images, etc are placed in the `assets` directory.
   - **Image Optimization**: Images in `assets/img` are automatically processed and converted to WebP.
   - **S3 Upload**: If configured in `.env`, processed images are uploaded to the specified S3 bucket.

8. Web Feeds (RSS / Atom)
   - Feeds are dynamically generated during build. You can customize them in `config.yaml` using the `feeds` key:
     ```yaml
     feeds:
       - filename: "feed.xml"
         layouts: ["post"]
         title: "My Site Feed"
         subtitle: "A collection of my thoughts and findings"
         content: true # Set to true to include the full HTML content of each post
     ```
   - **Default Feeds**: If the `feeds` key is omitted, three feeds will be generated: `/feed.xml` (all posts and TILs), `/blog/feed.xml` (blog posts only), and `/til/feed.xml` (TIL posts only).
   - **Excluding Pages**: Add `feed: false` to a markdown page's frontmatter to exclude it from all feeds.
   - **Styling**: The feed uses `public/pretty-feed-v3.xsl` to render beautifully when opened directly in a browser.

9. Run the development server

   ```bash
   npm run dev
   ```

10. Build the site for production

   ```bash
   npm run build
   ```
