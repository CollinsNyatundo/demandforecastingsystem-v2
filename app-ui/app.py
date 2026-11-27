"""UrbanFlow Intelligence — Multi-page Dash Application Shell.

This is the slim app factory that wires together:
- Multi-page routing (Dash pages)
- Persistent sidebar navigation
- Floating AI chat widget (Grok)
- Flask health/readiness endpoints
"""

import logging
import os
from datetime import datetime

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, ctx, dcc, html
from flask import jsonify

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Import shared state
from config_theme import app_state

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    use_pages=True,
    external_stylesheets=[
        dbc.themes.DARKLY,
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
        "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap",
    ],
    suppress_callback_exceptions=True,
    title="UrbanFlow Intelligence",
    update_title="⏳ Loading…",
)
server = app.server

# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------
from components.chat_widget import create_chat_widget
from components.navbar import create_navbar
from components.sidebar import create_sidebar

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        # Sidebar
        create_sidebar(),
        # Main content area
        html.Div(
            [
                create_navbar(),
                html.Main(
                    dash.page_container,
                    className="main-content",
                ),
            ],
            className="content-area",
        ),
        # Floating AI Chat Widget (available on all pages)
        create_chat_widget(),
    ],
    className="app-wrapper",
)


# ---------------------------------------------------------------------------
# Chat callbacks
# ---------------------------------------------------------------------------
@callback(
    Output("chat-panel", "style"),
    Output("chat-visible-store", "data"),
    Input("chat-fab", "n_clicks"),
    Input("chat-close", "n_clicks"),
    State("chat-visible-store", "data"),
    prevent_initial_call=True,
)
def toggle_chat(fab_clicks, close_clicks, visible):
    triggered = ctx.triggered_id
    if triggered == "chat-fab":
        new_visible = not visible
    elif triggered == "chat-close":
        new_visible = False
    else:
        new_visible = visible
    style = {"display": "flex"} if new_visible else {"display": "none"}
    return style, new_visible


@callback(
    Output("chat-suggestions", "children"),
    Input("url", "pathname"),
)
def update_suggestions(pathname):
    from components.chat_widget import PAGE_PROMPTS

    prompts = PAGE_PROMPTS.get(pathname, PAGE_PROMPTS.get("/", []))
    return [
        html.Button(
            p, className="chat-suggestion-chip", id={"type": "suggestion", "index": i}
        )
        for i, p in enumerate(prompts)
    ]


# ---------------------------------------------------------------------------
# Client-side Chat Callbacks (SSE Streaming)
# ---------------------------------------------------------------------------
app.clientside_callback(
    """
    function(send_clicks, n_submit, message, history, pathname, current_messages) {
        if (!message || message.trim() === "") {
            return window.dash_clientside.no_update;
        }
        // Defer execution to the custom script in assets/chat_stream.js
        if (window.UrbanFlow && window.UrbanFlow.streamChat) {
            window.UrbanFlow.streamChat(message, history, pathname);
        }

        // Return clear input and preserve history state (JS manages DOM and history via window object)
        return ["", window.dash_clientside.no_update];
    }
    """,
    Output("chat-input", "value"),
    Output("chat-history-store", "data"),
    Input("chat-send", "n_clicks"),
    Input("chat-input", "n_submit"),
    State("chat-input", "value"),
    State("chat-history-store", "data"),
    State("url", "pathname"),
    State("chat-messages", "children"),
    prevent_initial_call=True,
)


def _build_page_context(pathname: str) -> str:
    """Build context string based on current page."""
    from config_theme import df

    context_parts = [f"Current page: {pathname}"]

    if not df.empty and "cnt" in df.columns:
        context_parts.append(f"Total demand in dataset: {df['cnt'].sum():,.0f}")
        context_parts.append(f"Dataset rows: {len(df)}")

    try:
        from api_client import get_all_service_health, get_drift_metrics

        services = get_all_service_health()
        healthy = sum(1 for s in services if s.get("healthy"))
        context_parts.append(f"Services healthy: {healthy}/{len(services)}")

        drift = get_drift_metrics()
        if drift:
            context_parts.append(
                f"Drift share: {drift.get('evidently_drift_share', 0):.1%}"
            )
            context_parts.append(
                f"Dataset drift detected: {'Yes' if drift.get('evidently_dataset_drift', 0) > 0 else 'No'}"
            )
    except Exception:
        context_parts.append("Backend services: not connected (demo mode)")

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Flask health and proxy endpoints
# ---------------------------------------------------------------------------
from flask import Response, request, stream_with_context


@server.route("/chat/stream", methods=["POST"])
def proxy_chat_stream():
    import requests

    from api_client import MODEL_API_KEY, MODEL_SERVER_URL

    data = request.json

    def generate():
        try:
            resp = requests.post(
                f"{MODEL_SERVER_URL}/chat/stream",
                json=data,
                headers={
                    "X-API-Key": MODEL_API_KEY,
                    "Content-Type": "application/json",
                },
                stream=True,
                timeout=60,
            )
            for chunk in resp.iter_content(chunk_size=None):
                if chunk:
                    yield chunk
        except Exception as e:
            yield f'data: {{"error": "{e!s}"}}\n\n'.encode()

    return Response(stream_with_context(generate()), content_type="text/event-stream")


@server.route("/health")
def health_check():
    from datetime import UTC

    return jsonify(
        {
            "status": "healthy",
            "service": "demand-forecasting-ui",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )


@server.route("/ready")
def readiness_check():
    from datetime import UTC

    is_ready = app_state["data_loaded"] and app_state["error"] is None
    return (
        jsonify(
            {
                "ready": is_ready,
                "checks": {
                    "data_loaded": app_state["data_loaded"],
                    "no_errors": app_state["error"] is None,
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ),
        200 if is_ready else 503,
    )


@server.route("/metrics")
def metrics():
    import psutil

    process = psutil.Process()
    mem_info = process.memory_info()
    cpu_percent = process.cpu_percent()

    return Response(
        f"dash_app_memory_bytes {mem_info.rss}\ndash_app_cpu_percent {cpu_percent}\n",
        mimetype="text/plain",
    )


@server.route("/reports/<path:filename>")
def serve_report(filename):
    import os

    from flask import send_from_directory

    from config_theme import project_root

    reports_dir = os.path.join(project_root, "app-ml", "data", "09_reports")
    return send_from_directory(reports_dir, filename)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    debug_mode = os.environ.get("DASH_DEBUG", "false").lower() == "true"
    logger.info(f"Starting UrbanFlow Intelligence Dashboard (debug={debug_mode})")
    app.run(debug=debug_mode, use_reloader=debug_mode, host="0.0.0.0", port=8050)
