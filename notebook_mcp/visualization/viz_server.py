"""
On-demand visualization web server.

Starts an HTTP server in a background thread on the first call to
open_visualization() or open_gallery(). Serves notebook visualizations
as interactive HTML pages in the user's browser.

No external dependencies required (uses Python stdlib http.server).
Optional: if flask is installed, uses it for better error handling.
"""

import base64
import hashlib
import html
import json
import logging
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

log = logging.getLogger(__name__)

DEFAULT_PORT = 9981
_server_thread: Optional[threading.Thread] = None
_httpd: Optional[HTTPServer] = None
_viz_cache: Dict[str, Any] = {}  # key -> rendered HTML


def _make_key(filepath: str, cell_index: int) -> str:
    """Generate a URL-safe cache key."""
    raw = f"{os.path.realpath(filepath)}:{cell_index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _gallery_key(filepath: str) -> str:
    """Generate a URL-safe gallery key."""
    raw = os.path.realpath(filepath)
    return "gallery_" + hashlib.md5(raw.encode()).hexdigest()[:12]


def _render_image_page(title: str, mime: str, data: str, description: str = "") -> str:
    """Render an HTML page with a single image and description."""
    if mime == "image/svg+xml":
        img_tag = f'<div class="svg-container">{data}</div>'
    else:
        img_tag = f'<img src="data:{mime};base64,{data}" alt="{html.escape(title)}" style="max-width:100%;height:auto;">'

    desc_html = f'<div class="description"><p>{html.escape(description)}</p></div>' if description else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #1e1e1e; color: #d4d4d4;
          margin: 0; padding: 20px; }}
  h1 {{ font-size: 1.2em; color: #9cdcfe; margin-bottom: 10px; }}
  .viz-container {{ background: #252526; border-radius: 8px; padding: 16px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.4); }}
  .description {{ margin-top: 16px; background: #2d2d2d; border-left: 3px solid #007acc;
                  padding: 12px; border-radius: 4px; font-size: 0.9em; line-height:1.5; }}
  .svg-container svg {{ max-width:100%; height:auto; }}
  img {{ display:block; margin:auto; border-radius:4px; }}
  .meta {{ font-size:0.75em; color:#858585; margin-top:8px; }}
</style>
</head>
<body>
<div class="viz-container">
  <h1>{html.escape(title)}</h1>
  {img_tag}
  {desc_html}
  <div class="meta">Served by Notebook MCP Visualization Server</div>
</div>
</body>
</html>"""


def _render_html_page(title: str, content: str, description: str = "") -> str:
    """Render an HTML page wrapping arbitrary HTML content (e.g. Plotly)."""
    desc_html = f'<div class="description"><p>{html.escape(description)}</p></div>' if description else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #1e1e1e; color: #d4d4d4;
          margin: 0; padding: 0; }}
  .header {{ padding: 12px 20px; background: #252526; border-bottom: 1px solid #333; }}
  h1 {{ font-size: 1.1em; color: #9cdcfe; margin: 0; }}
  .content {{ padding: 16px; }}
  .description {{ margin: 12px 16px; background: #2d2d2d; border-left: 3px solid #007acc;
                  padding: 12px; border-radius: 4px; font-size: 0.9em; }}
</style>
</head>
<body>
<div class="header"><h1>{html.escape(title)}</h1></div>
{desc_html}
<div class="content">{content}</div>
</body>
</html>"""


def _render_gallery_page(notebook_name: str, items: list) -> str:
    """Render a gallery of all visualizations from a notebook."""
    items_html = ""
    for item in items:
        key = item.get("key", "")
        cell_idx = item.get("cell_index", "?")
        chart_type = item.get("chart_type") or "visualization"
        lib = item.get("library") or ""
        desc = item.get("description", "")
        thumb = item.get("thumbnail", "")

        if thumb:
            img = f'<img src="data:image/png;base64,{thumb}" alt="Cell {cell_idx}" style="max-width:100%;height:auto;">'
        else:
            img = f'<div class="no-thumb">Cell {cell_idx}<br>({chart_type})</div>'

        items_html += f"""
<div class="viz-card" onclick="window.location='/viz/{key}'">
  <div class="thumb">{img}</div>
  <div class="info">
    <div class="idx">Cell {cell_idx}</div>
    <div class="type">{html.escape(chart_type)} {f'({lib})' if lib else ''}</div>
    <div class="desc">{html.escape(desc[:120])}</div>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Notebook Gallery – {html.escape(notebook_name)}</title>
<style>
  body {{ font-family:system-ui,sans-serif; background:#1e1e1e; color:#d4d4d4;
          margin:0; padding:20px; }}
  h1 {{ color:#9cdcfe; font-size:1.3em; }}
  .grid {{ display:flex; flex-wrap:wrap; gap:16px; margin-top:16px; }}
  .viz-card {{ background:#252526; border-radius:8px; padding:12px; cursor:pointer;
               width:280px; border:1px solid #333; transition:border-color .2s; }}
  .viz-card:hover {{ border-color:#007acc; }}
  .thumb {{ background:#1a1a1a; border-radius:4px; overflow:hidden; min-height:120px;
            display:flex; align-items:center; justify-content:center; }}
  .no-thumb {{ color:#858585; text-align:center; font-size:0.85em; padding:20px; }}
  .info {{ margin-top:10px; }}
  .idx {{ font-weight:bold; color:#9cdcfe; font-size:0.85em; }}
  .type {{ color:#ce9178; font-size:0.8em; }}
  .desc {{ font-size:0.75em; color:#858585; margin-top:4px; line-height:1.4; }}
  .empty {{ color:#858585; padding:40px; text-align:center; }}
</style>
</head>
<body>
<h1>Notebook Gallery</h1>
<p style="color:#858585;font-size:0.85em;">{html.escape(notebook_name)}</p>
<div class="grid">
{items_html if items_html else '<div class="empty">No visualizations found in this notebook.</div>'}
</div>
</body>
</html>"""


class _VizHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler that serves cached visualization pages."""

    def log_message(self, fmt, *args):
        log.debug("viz-server: " + fmt, *args)

    def _send_html(self, content: str, status: int = 200):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")

        if path == "" or path == "/":
            self._send_html("<h1>Notebook MCP Visualization Server</h1><p>Running.</p>")
            return

        # /viz/{key} — single visualization
        if path.startswith("/viz/"):
            key = path[5:]
            if key in _viz_cache:
                self._send_html(_viz_cache[key])
            else:
                self._send_html("<h1>404</h1><p>Visualization not found or not yet rendered.</p>", 404)
            return

        self._send_html("<h1>404</h1><p>Not found.</p>", 404)


def ensure_server_running(port: int = DEFAULT_PORT) -> str:
    """Start the visualization server if it isn't already running.

    Returns the base URL of the server.
    """
    global _server_thread, _httpd

    if _httpd is not None:
        return f"http://127.0.0.1:{port}"

    try:
        _httpd = HTTPServer(("127.0.0.1", port), _VizHandler)
    except OSError:
        # Port in use — try next port
        for p in range(port + 1, port + 20):
            try:
                _httpd = HTTPServer(("127.0.0.1", p), _VizHandler)
                port = p
                break
            except OSError:
                continue
        else:
            raise RuntimeError("Could not find a free port for the visualization server.")

    _server_thread = threading.Thread(target=_httpd.serve_forever, daemon=True)
    _server_thread.start()
    log.info("Visualization server started at http://127.0.0.1:%d", port)
    return f"http://127.0.0.1:{port}"


def cache_and_open_visualization(
    filepath: str,
    cell_index: int,
    html_content: str,
    open_browser: bool = True,
    port: int = DEFAULT_PORT,
) -> str:
    """Cache rendered HTML for a visualization and return its URL.

    Args:
        filepath:     Notebook path (used to generate the URL key).
        cell_index:   Cell index.
        html_content: Fully rendered HTML string.
        open_browser: If True, open the URL in the default browser.
        port:         Visualization server port.

    Returns:
        URL to the visualization page.
    """
    base_url = ensure_server_running(port)
    key = _make_key(filepath, cell_index)
    _viz_cache[key] = html_content
    url = f"{base_url}/viz/{key}"
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as e:
            log.warning("Could not open browser: %s", e)
    return url


def cache_and_open_gallery(
    filepath: str,
    gallery_html: str,
    open_browser: bool = True,
    port: int = DEFAULT_PORT,
) -> str:
    """Cache a gallery page and return its URL."""
    base_url = ensure_server_running(port)
    key = _gallery_key(filepath)
    _viz_cache[key] = gallery_html
    url = f"{base_url}/viz/{key}"
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as e:
            log.warning("Could not open browser: %s", e)
    return url


def render_cell_to_html(
    cell: Any,
    cell_index: int,
    notebook_name: str,
    description: str = "",
) -> Optional[str]:
    """Render a cell's visual output as an HTML page.

    Returns the rendered HTML string, or None if no visual output found.
    """
    from notebook_mcp.visualization.detector import get_image_data, get_html_output
    from notebook_mcp.visualization.image_handler import get_cell_image

    title = f"Cell {cell_index} – {notebook_name}"

    # Prefer HTML output (interactive plots like Plotly)
    html_out = get_html_output(cell)
    if html_out:
        return _render_html_page(title, html_out, description)

    # Fall back to raster image
    img = get_cell_image(cell)
    if img:
        return _render_image_page(title, img["mime"], img["data"], description)

    return None
