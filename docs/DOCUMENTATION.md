# Documentation System

## Overview

The S3 ACID Database now includes beautiful, professional HTML documentation served directly from the same FastAPI/Lambda container.

## Architecture

**Simple & Lightweight Approach:**
- ✅ Pure Python - no Node.js required
- ✅ Converts MDX/Markdown to HTML on-the-fly
- ✅ Modern dark theme with syntax highlighting
- ✅ Works in both development and production (Lambda)
- ✅ ~300KB total size impact

## How It Works

1. **Markdown files** are stored in `docs/mintlify/*.mdx`
2. **Python renderer** (`src/docs_renderer.py`) converts them to HTML
3. **FastAPI serves** the HTML at `/documentation` endpoints
4. **Docker bundles** docs into the container image

## Components

### 1. Documentation Files (`docs/mintlify/`)
```
docs/mintlify/
├── mint.json                # Configuration
├── introduction.mdx         # Landing page
├── quickstart.mdx          # Getting started
├── installation.mdx        # Installation guide
├── api/
│   ├── overview.mdx        # API overview
│   ├── create-table.mdx    # CREATE_TABLE
│   ├── write.mdx           # WRITE
│   └── query.mdx           # QUERY
├── features/
│   ├── aggregations.mdx    # Type-safe aggregations
│   └── versioning.mdx      # Version history
└── examples/
    ├── basic-crud.mdx      # CRUD examples
    └── analytics.mdx       # Analytics examples
```

### 2. HTML Renderer (`src/docs_renderer.py`)

**Features:**
- Converts Markdown/MDX to HTML
- Syntax highlighting with Pygments
- Handles MDX components (`<Note>`, `<Tip>`, `<Warning>`, `<Card>`, `<Step>`)
- Dark theme with modern styling
- Responsive design

**Key Functions:**
- `render_markdown_to_html()` - Main rendering function
- `convert_mdx_special_components()` - Converts MDX tags to HTML
- `get_html_template()` - Returns styled HTML template

### 3. FastAPI Routes (`fastapi_app.py`)

**Documentation Endpoints:**
- `GET /documentation` - Landing page (introduction)
- `GET /documentation/config` - Configuration JSON
- `GET /documentation/{page}` - Root-level pages (quickstart, installation)
- `GET /documentation/{category}/{page}` - Nested pages (api/query, features/aggregations)

## Access Documentation

### Development (Docker Compose)
```bash
cd docker
docker compose up -d fastapi

# Access docs
open http://localhost:9000/documentation
```

**Available pages:**
- http://localhost:9000/documentation - Home
- http://localhost:9000/documentation/quickstart - Quickstart
- http://localhost:9000/documentation/api/query - API docs
- http://localhost:9000/documentation/features/aggregations - Features
- http://localhost:9000/documentation/features/versioning - Versioning

### Production (AWS Lambda)

The same Docker image works in Lambda! Just deploy with:
- Lambda Function URL or API Gateway
- Access via: `https://your-api.com/documentation`

## Adding New Documentation

1. **Create MDX file** in appropriate directory:
```mdx
---
title: Your Page Title
description: 'Brief description'
---

# Your Page Title

Your content here with **markdown** support!

<Note>
Important information
</Note>

\`\`\`json
{
  "example": "code block"
}
\`\`\`
```

2. **Add to navigation** in `mint.json`:
```json
{
  "navigation": [
    {
      "group": "Your Group",
      "pages": ["your-page"]
    }
  ]
}
```

3. **Rebuild Docker** (if needed):
```bash
docker compose build fastapi
docker compose up -d fastapi
```

## Styling

**Color Scheme:**
- Primary: `#0D9373` (Teal green)
- Primary Light: `#07C983` (Light green)
- Background: `#0f1117` (Dark blue-gray)
- Cards: `#1a1d29` (Slightly lighter)
- Text: `#ffffff` / `#a0aec0`

**Supported Components:**
- `<Note>` - Blue info box
- `<Tip>` - Green tip box
- `<Warning>` - Yellow warning box
- `<Card>` - Content card
- `<Step>` - Step heading
- `<AccordionGroup>` / `<Accordion>` - Expandable sections

## Benefits Over Mintlify

**Our HTML Approach:**
- ✅ 100% Python, no Node.js
- ✅ Works perfectly in Lambda
- ✅ Small Docker image size
- ✅ Fast rendering
- ✅ No external dependencies
- ✅ Simple deployment

**vs Full Mintlify:**
- ❌ Requires Node.js + Next.js
- ❌ Large image size (~1-2GB)
- ❌ Complex multi-process setup
- ❌ More resource intensive

## Future Enhancements

Possible improvements:
1. **Search functionality** - Add client-side search
2. **Navigation sidebar** - Auto-generated from mint.json
3. **Code copy buttons** - One-click code copying
4. **Dark/light mode toggle** - User preference
5. **Analytics** - Track page views
6. **API playground integration** - Interactive API testing

## Maintenance

**Updating docs:**
1. Edit MDX files in `docs/mintlify/`
2. Commit changes
3. Rebuild and redeploy

**No build step required** - HTML is generated on-the-fly!
