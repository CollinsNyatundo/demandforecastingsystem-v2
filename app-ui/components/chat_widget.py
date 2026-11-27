"""Floating AI chat widget — rendered in the app shell, available on every page."""

from dash import dcc, html

from config_theme import THEME

# Per-page suggested prompts
PAGE_PROMPTS = {
    "/": [
        "Give me a system health overview",
        "What's the current demand trend?",
        "How is model accuracy?",
    ],
    "/dashboard": [
        "Why is accuracy dropping?",
        "Should we retrain the model?",
        "Explain this forecast pattern",
    ],
    "/predictions": [
        "What features drive demand most?",
        "Is this prediction reliable?",
        "How does weather affect ridership?",
    ],
    "/model-metrics": [
        "Interpret this drift score",
        "Compare performance to last month",
        "When should we retrain?",
    ],
}


def create_chat_widget():
    """Build the floating FAB + slide-up chat panel. Rendered once in app.py layout."""
    return html.Div(
        [
            # FAB (Floating Action Button)
            html.Button(
                html.Div(
                    [
                        html.I(className="bi bi-robot", style={"fontSize": "1.3rem"}),
                    ],
                ),
                id="chat-fab",
                className="chat-fab",
                n_clicks=0,
            ),
            # Chat Panel (hidden by default)
            html.Div(
                [
                    # Header
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="bi bi-robot me-2",
                                        style={"color": THEME["cyan"]},
                                    ),
                                    html.Span(
                                        "UrbanFlow AI", className="fw-bold text-white"
                                    ),
                                ],
                                className="d-flex align-items-center",
                            ),
                            html.Button(
                                html.I(className="bi bi-x-lg"),
                                id="chat-close",
                                className="chat-close-btn",
                                n_clicks=0,
                            ),
                        ],
                        className="chat-header",
                    ),
                    # Messages area
                    html.Div(
                        [
                            # Welcome message
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.I(
                                                className="bi bi-robot me-2",
                                                style={
                                                    "color": THEME["cyan"],
                                                    "fontSize": "0.85rem",
                                                },
                                            ),
                                            html.Span(
                                                "Hi! I'm UrbanFlow AI. Ask me about demand patterns, "
                                                "model health, or optimization strategies.",
                                                className="small",
                                            ),
                                        ],
                                        className="chat-bubble chat-bubble-ai",
                                    ),
                                ],
                            ),
                        ],
                        id="chat-messages",
                        className="chat-messages",
                    ),
                    # Suggested prompts
                    html.Div(id="chat-suggestions", className="chat-suggestions"),
                    # Input bar
                    html.Div(
                        [
                            dcc.Input(
                                id="chat-input",
                                type="text",
                                placeholder="Ask about demand, drift, models…",
                                className="chat-input-field",
                                maxLength=500,
                                debounce=True,
                            ),
                            html.Button(
                                html.I(className="bi bi-send-fill"),
                                id="chat-send",
                                className="chat-send-btn",
                                n_clicks=0,
                            ),
                        ],
                        className="chat-input-bar",
                    ),
                ],
                id="chat-panel",
                className="chat-panel",
                style={"display": "none"},
            ),
            # Client-side stores
            dcc.Store(id="chat-history-store", data=[]),
            dcc.Store(id="chat-visible-store", data=False),
            dcc.Store(id="chat-page-context", data=""),
        ],
        className="chat-widget-container",
    )
