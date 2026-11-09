---
title: "Configuration & Themes"
section: "Guide"
order: 3
---

Your site configuration is managed in `config.yaml` located at the root of your project.

## Basic Settings

```yaml
site_name: "My Site"
author: "Your Name"
base_url: "https://example.com"
```

## DaisyUI Themes

Configure pre-built DaisyUI themes or define custom color palettes:

```yaml
theme:
  default: "dracula"
  include:
    - "dracula"
    - "light"
    - "dark"
```

Themes are automatically injected into CSS at build time and can be switched dynamically with the theme selector dropdown.

## Navigation Links

Define the header navigation menu:

```yaml
navigation:
  - name: "Home"
    url: "/"
  - name: "Blog"
    url: "/blog/"
  - name: "Docs"
    url: "/docs/"
```
