#!/usr/bin/env python3
"""
FastAPI Entry Point for S3 ACID Database
Wraps Lambda handler for local development without Lambda emulator bugs
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import Lambda handler - we'll reuse its logic
from src.lambda_handler import lambda_handler
from src.docs_renderer import render_markdown_to_html, get_page_title_from_content

# Initialize FastAPI app
app = FastAPI(
    title="S3 ACID Database API",
    description="Production-ready ACID database on S3 with Apache Iceberg, DuckDB, and PyIceberg",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for Mintlify documentation
DOCS_DIR = Path(__file__).parent / "docs" / "mintlify"
if DOCS_DIR.exists():
    app.mount("/mintlify-static", StaticFiles(directory=str(DOCS_DIR)), name="mintlify-docs")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "S3 ACID Database",
        "version": "1.0.0",
        "status": "healthy",
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "mintlify": "/documentation",
            "config": "/documentation/config",
            "examples": {
                "quickstart": "/documentation/quickstart",
                "api_query": "/documentation/api/query",
                "aggregations": "/documentation/features/aggregations",
                "versioning": "/documentation/features/versioning"
            }
        },
        "endpoints": {
            "health": "GET /health",
            "documentation": "GET /documentation",
            "query": "POST /database",
            "write": "POST /database",
            "update": "POST /database",
            "delete": "POST /database",
            "compact": "POST /database",
            "create_table": "POST /database",
            "list_tables": "POST /database",
            "describe_table": "POST /database"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint - calls Lambda handler"""
    event = {
        "httpMethod": "GET",
        "path": "/health"
    }
    response = lambda_handler(event, None)
    return JSONResponse(
        status_code=response["statusCode"],
        content=json.loads(response["body"])
    )


@app.get("/documentation")
async def get_documentation_index():
    """
    Serve documentation landing page (introduction)
    Renders markdown/MDX to beautiful HTML
    """
    intro_file = DOCS_DIR / "introduction.mdx"
    if intro_file.exists():
        content = intro_file.read_text()
        title = get_page_title_from_content(content)
        html = render_markdown_to_html(content, title)
        return HTMLResponse(content=html)

    return JSONResponse(
        status_code=404,
        content={"error": "Documentation not found"}
    )


@app.get("/documentation/config")
async def get_documentation_config():
    """Serve documentation configuration (mint.json)"""
    config_file = DOCS_DIR / "mint.json"
    if config_file.exists():
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return JSONResponse(content=config_data)
    return JSONResponse(
        status_code=404,
        content={"error": "Documentation config not found"}
    )


@app.get("/documentation/{category}/{page}")
async def get_documentation_page(category: str, page: str):
    """
    Serve specific documentation page as HTML
    Example: /documentation/api/query -> renders docs/mintlify/api/query.mdx
    """
    # Sanitize inputs to prevent directory traversal
    safe_category = category.replace("..", "").replace("/", "")
    safe_page = page.replace("..", "").replace("/", "")

    page_file = DOCS_DIR / safe_category / f"{safe_page}.mdx"
    if page_file.exists():
        content = page_file.read_text()
        title = get_page_title_from_content(content)
        html = render_markdown_to_html(content, title)
        return HTMLResponse(content=html)

    return JSONResponse(
        status_code=404,
        content={"error": f"Documentation page {category}/{page} not found"}
    )


@app.get("/documentation/{page}")
async def get_documentation_root_page(page: str):
    """
    Serve root-level documentation page as HTML
    Example: /documentation/quickstart -> renders docs/mintlify/quickstart.mdx
    """
    # Sanitize input to prevent directory traversal
    safe_page = page.replace("..", "").replace("/", "")

    page_file = DOCS_DIR / f"{safe_page}.mdx"
    if page_file.exists():
        content = page_file.read_text()
        title = get_page_title_from_content(content)
        html = render_markdown_to_html(content, title)
        return HTMLResponse(content=html)

    return JSONResponse(
        status_code=404,
        content={"error": f"Documentation page {page} not found"}
    )


@app.post("/database")
async def database_operation(request: Request):
    """
    Main database endpoint - wraps Lambda handler
    Accepts any database operation and routes through Lambda handler logic
    """
    body = await request.json()

    # Convert FastAPI request to Lambda event format
    event = {
        "httpMethod": "POST",
        "path": "/database",
        "body": json.dumps(body)
    }

    # Call Lambda handler
    response = lambda_handler(event, None)

    # Convert Lambda response to FastAPI response
    return JSONResponse(
        status_code=response["statusCode"],
        content=json.loads(response["body"])
    )


if __name__ == "__main__":
    import uvicorn

    # Set environment
    os.environ.setdefault("ENVIRONMENT", "development")

    print("="*60)
    print("S3 ACID Database - FastAPI Server")
    print("="*60)
    print(f"Environment: {os.environ.get('ENVIRONMENT')}")
    print(f"Server: http://localhost:8000")
    print(f"Docs: http://localhost:8000/docs")
    print(f"Health: http://localhost:8000/health")
    print("="*60)

    # Run server
    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
