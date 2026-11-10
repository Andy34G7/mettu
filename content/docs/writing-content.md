---
title: "Writing Content & Docs"
section: "Authoring"
order: 4
---

Authoring content in `mettu` is designed to be intuitive and expressive.

## Scaffolding New Content

You can quickly scaffold new posts, pages, or docs using the CLI:

```bash
npm run new -- "My New Post"
npm run new -- --kind doc "API Reference"
```

## Callouts & Admonitions

`mettu` supports GitHub-style callouts for highlighting important information.

Here is an informational note:

> [!NOTE]
> This is an informational note highlighting useful background details.

You can also provide helpful tips:

> [!TIP]
> Pro tip: You can use `⌘K` or `Ctrl+K` on any documentation page to instantly search across all headings and pages.

Or alert readers to potential pitfalls:

> [!WARNING]
> Do not modify files in `dist/` directly, as they are overwritten on every build.

## Code Blocks & Syntax Highlighting

Fenced code blocks with language identifiers are highlighted with Pygments:

```python
def hello_world():
    print("Welcome to mettu docs!")
```

Every code block automatically includes a one-click **Copy** button.
