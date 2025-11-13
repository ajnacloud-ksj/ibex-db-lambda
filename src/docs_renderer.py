"""
HTML Documentation Renderer
Converts MDX/Markdown files to beautiful HTML with syntax highlighting
"""

import json
import re
from pathlib import Path
from typing import Optional
import markdown
from markdown.extensions import fenced_code, tables, toc, codehilite
from pygments.formatters import HtmlFormatter


def get_html_template() -> str:
    """Returns the base HTML template with modern styling"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - S3 ACID Database</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --primary: #0D9373;
            --primary-light: #07C983;
            --bg-dark: #0f1117;
            --bg-card: #1a1d29;
            --text-primary: #ffffff;
            --text-secondary: #a0aec0;
            --border: #2d3748;
            --code-bg: #1e2433;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        .header {{
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
            padding: 1rem 0;
            margin-bottom: 2rem;
        }}

        .header-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .logo {{
            font-size: 1.5rem;
            font-weight: bold;
            color: var(--primary);
            text-decoration: none;
        }}

        .nav {{
            display: flex;
            gap: 2rem;
        }}

        .nav a {{
            color: var(--text-secondary);
            text-decoration: none;
            transition: color 0.2s;
        }}

        .nav a:hover {{
            color: var(--primary);
        }}

        .content {{
            background: var(--bg-card);
            border-radius: 8px;
            padding: 3rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}

        h1 {{
            font-size: 2.5rem;
            margin-bottom: 1rem;
            color: var(--primary);
        }}

        h2 {{
            font-size: 2rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: var(--text-primary);
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
        }}

        h3 {{
            font-size: 1.5rem;
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
            color: var(--text-primary);
        }}

        h4 {{
            font-size: 1.25rem;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
        }}

        p {{
            margin-bottom: 1rem;
            color: var(--text-secondary);
        }}

        a {{
            color: var(--primary-light);
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        code {{
            background: var(--code-bg);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 0.9em;
            color: var(--primary-light);
        }}

        pre {{
            background: var(--code-bg);
            padding: 1.5rem;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1rem 0;
            border-left: 4px solid var(--primary);
        }}

        pre code {{
            background: none;
            padding: 0;
            color: var(--text-primary);
        }}

        ul, ol {{
            margin: 1rem 0;
            padding-left: 2rem;
            color: var(--text-secondary);
        }}

        li {{
            margin: 0.5rem 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
        }}

        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }}

        th {{
            background: var(--code-bg);
            color: var(--primary);
            font-weight: 600;
        }}

        tr:hover {{
            background: rgba(13, 147, 115, 0.05);
        }}

        .note {{
            background: rgba(13, 147, 115, 0.1);
            border-left: 4px solid var(--primary);
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}

        .tip {{
            background: rgba(7, 201, 131, 0.1);
            border-left: 4px solid var(--primary-light);
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}

        .warning {{
            background: rgba(255, 193, 7, 0.1);
            border-left: 4px solid #ffc107;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}

        blockquote {{
            border-left: 4px solid var(--primary);
            padding-left: 1rem;
            margin: 1rem 0;
            color: var(--text-secondary);
            font-style: italic;
        }}

        .sidebar {{
            position: fixed;
            right: 2rem;
            top: 6rem;
            width: 250px;
            background: var(--bg-card);
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}

        .sidebar h3 {{
            font-size: 1rem;
            margin-bottom: 1rem;
            color: var(--primary);
        }}

        .sidebar ul {{
            list-style: none;
            padding: 0;
        }}

        .sidebar li {{
            margin: 0.5rem 0;
        }}

        .sidebar a {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        @media (max-width: 1024px) {{
            .sidebar {{
                display: none;
            }}
        }}

        {pygments_css}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <a href="/documentation" class="logo">S3 ACID Database</a>
            <nav class="nav">
                <a href="/documentation">Home</a>
                <a href="/documentation/quickstart">Quickstart</a>
                <a href="/documentation/api/query">API</a>
                <a href="/">API Playground</a>
            </nav>
        </div>
    </div>

    <div class="container">
        <div class="content">
            {content}
        </div>
    </div>
</body>
</html>"""


def convert_mdx_special_components(content: str) -> str:
    """Convert MDX special components to HTML"""

    # Convert <Note> to styled div
    content = re.sub(
        r'<Note>(.*?)</Note>',
        r'<div class="note">\1</div>',
        content,
        flags=re.DOTALL
    )

    # Convert <Tip> to styled div
    content = re.sub(
        r'<Tip>(.*?)</Tip>',
        r'<div class="tip">\1</div>',
        content,
        flags=re.DOTALL
    )

    # Convert <Warning> to styled div
    content = re.sub(
        r'<Warning>(.*?)</Warning>',
        r'<div class="warning">\1</div>',
        content,
        flags=re.DOTALL
    )

    # Remove <Steps> tags (keep content)
    content = re.sub(r'<Steps>', '', content)
    content = re.sub(r'</Steps>', '', content)

    # Convert <Step title="..."> to h3
    content = re.sub(
        r'<Step title="([^"]+)">',
        r'<h3>\1</h3>',
        content
    )
    content = re.sub(r'</Step>', '', content)

    # Remove <CardGroup> tags (keep content)
    content = re.sub(r'<CardGroup[^>]*>', '', content)
    content = re.sub(r'</CardGroup>', '', content)

    # Convert <Card> to simple div
    content = re.sub(
        r'<Card title="([^"]+)"[^>]*>',
        r'<div class="note"><strong>\1</strong><br>',
        content
    )
    content = re.sub(r'</Card>', '</div>', content)

    # Remove <Accordion> tags (keep content as expandable sections)
    content = re.sub(
        r'<Accordion title="([^"]+)">',
        r'<details><summary><strong>\1</strong></summary>',
        content
    )
    content = re.sub(r'</Accordion>', '</details>', content)
    content = re.sub(r'<AccordionGroup>', '', content)
    content = re.sub(r'</AccordionGroup>', '', content)

    return content


def render_markdown_to_html(content: str, title: str = "Documentation") -> str:
    """Convert markdown/MDX content to HTML"""

    # Remove frontmatter
    content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

    # Convert MDX special components
    content = convert_mdx_special_components(content)

    # Initialize markdown with extensions
    md = markdown.Markdown(
        extensions=[
            'fenced_code',
            'tables',
            'toc',
            'codehilite',
            'nl2br',
            'sane_lists'
        ],
        extension_configs={
            'codehilite': {
                'css_class': 'highlight',
                'linenums': False,
                'guess_lang': False
            }
        }
    )

    # Convert markdown to HTML
    html_content = md.convert(content)

    # Get Pygments CSS for syntax highlighting
    formatter = HtmlFormatter(style='monokai')
    pygments_css = formatter.get_style_defs('.highlight')

    # Render full HTML page
    template = get_html_template()
    return template.format(
        title=title,
        content=html_content,
        pygments_css=pygments_css
    )


def get_page_title_from_content(content: str) -> str:
    """Extract title from markdown frontmatter or first H1"""

    # Try to get from frontmatter
    frontmatter_match = re.search(r'^---\n.*?title:\s*["\']?([^"\'\n]+)["\']?.*?\n---', content, re.DOTALL)
    if frontmatter_match:
        return frontmatter_match.group(1)

    # Try to get first H1
    h1_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if h1_match:
        return h1_match.group(1)

    return "Documentation"
