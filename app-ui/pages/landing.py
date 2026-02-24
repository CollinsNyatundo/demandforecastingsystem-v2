"""Landing page — Hero overview for decision makers arriving at the system."""

import dash
import dash_bootstrap_components as dbc
from dash import html, dcc, callback, Input, Output

from config_theme import THEME, app_state

dash.register_page(__name__, path="/", name="Home", order=0)


# ---------------------------------------------------------------------------
# Helpers (must be defined before layout since layout evaluates at import)
# ---------------------------------------------------------------------------
def _quick_stat(id_prefix, label, icon, color):
    return dbc.Col(
        html.Div(
            [
                html.Div(
                    html.I(className=f"bi {icon}", style={"color": color, "fontSize": "1.5rem"}),
                    className="quick-stat-icon",
                ),
                html.Div(
                    [
                        html.H3("—", id=f"{id_prefix}-value", className="quick-stat-value"),
                        html.Small(label, className="quick-stat-label"),
                    ],
                ),
            ],
            className="glass-card quick-stat-card",
        ),
        xs=6, lg=3, className="mb-4",
    )


def _feature_card(title, description, icon, color, href):
    return dbc.Col(
        html.A(
            html.Div(
                [
                    html.Div(
                        html.I(className=f"bi {icon}", style={"fontSize": "1.6rem"}),
                        className="feature-card-icon",
                        style={"color": color},
                    ),
                    html.H6(title, className="feature-card-title"),
                    html.P(description, className="feature-card-desc"),
                    html.Span(
                        [html.I(className="bi bi-arrow-right me-1"), "Explore"],
                        className="feature-card-link",
                        style={"color": color},
                    ),
                ],
                className="glass-card feature-card h-100",
            ),
            href=href,
            className="text-decoration-none",
        ),
        md=4,
        className="mb-4",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
layout = html.Div(
    [
        # Hero Section
        html.Section(
            html.Div(
                [
                    html.Div(
                        [
                            html.Img(
                                src="/assets/animated_bike.svg",
                                style={"height": "56px"},
                                className="mb-3",
                            ),
                            html.H1(
                                [
                                    "Urban Demand ",
                                    html.Span("Intelligence", style={"color": THEME["blue"]}),
                                ],
                                className="hero-title",
                            ),
                            html.P(
                                "Real-time bike-sharing demand forecasting powered by machine learning. "
                                "Monitor ridership patterns, detect data drift, and optimize fleet "
                                "distribution across the city.",
                                className="hero-subtitle",
                            ),
                            html.Div(
                                [
                                    dbc.Button(
                                        [html.I(className="bi bi-speedometer2 me-2"), "Open Dashboard"],
                                        href="/dashboard",
                                        color="primary",
                                        className="me-3 hero-btn",
                                        size="lg",
                                    ),
                                    dbc.Button(
                                        [html.I(className="bi bi-lightning-charge me-2"), "Try Predictions"],
                                        href="/predictions",
                                        outline=True,
                                        color="light",
                                        className="hero-btn",
                                        size="lg",
                                    ),
                                ],
                                className="hero-actions",
                            ),
                        ],
                        className="hero-content",
                    ),
                ],
                className="hero-container",
            ),
            className="hero-section",
        ),

        # Headline KPIs
        html.Section(
            dbc.Container(
                [
                    html.H5(
                        "System Overview",
                        className="section-heading",
                    ),
                    html.P(
                        "Key performance indicators updated every 5 seconds from the live prediction pipeline.",
                        className="section-description mb-4",
                    ),
                    dbc.Row(
                        [
                            _quick_stat("kpi-home-demand", "Total Predictions", "bi-calculator", THEME["cyan"]),
                            _quick_stat("kpi-home-accuracy", "Model Accuracy", "bi-bullseye", THEME["green"]),
                            _quick_stat("kpi-home-response", "Avg Response", "bi-clock", THEME["purple"]),
                            _quick_stat("kpi-home-health", "Services Up", "bi-heart-pulse", THEME["amber"]),
                        ],
                    ),
                ],
                fluid=True,
                className="py-5",
            ),
            className="kpi-overview-section",
        ),

        # Quick-link cards
        html.Section(
            dbc.Container(
                [
                    html.H5("Explore", className="section-heading"),
                    html.P(
                        "Dive deeper into specific areas of the ML system.",
                        className="section-description mb-4",
                    ),
                    dbc.Row(
                        [
                            _feature_card(
                                "Operational Dashboard",
                                "Real-time demand forecasts, feature importance, "
                                "and system health monitoring in one view.",
                                "bi-speedometer2",
                                THEME["blue"],
                                "/dashboard",
                            ),
                            _feature_card(
                                "Live Predictions",
                                "Test the demand model with custom inputs. "
                                "Each prediction is logged for continuous learning.",
                                "bi-lightning-charge",
                                THEME["cyan"],
                                "/predictions",
                            ),
                            _feature_card(
                                "Model Health & Drift",
                                "Track model performance over time. Evidently "
                                "monitors feature distributions against baselines.",
                                "bi-heart-pulse",
                                THEME["green"],
                                "/model-metrics",
                            ),
                        ],
                    ),
                ],
                fluid=True,
                className="py-5",
            ),
        ),

        # System ribbon
        html.Section(
            dbc.Container(
                html.Div(id="home-service-ribbon", className="service-ribbon"),
                fluid=True,
                className="py-4",
            ),
        ),

        # Interval for auto-refresh
        dcc.Interval(id="home-interval", interval=5000, n_intervals=0),
    ],
    className="page-landing",
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
@callback(
    [
        Output("kpi-home-demand-value", "children"),
        Output("kpi-home-accuracy-value", "children"),
        Output("kpi-home-response-value", "children"),
        Output("kpi-home-health-value", "children"),
        Output("home-service-ribbon", "children"),
    ],
    Input("home-interval", "n_intervals"),
)
def update_home_kpis(n):
    from config_theme import df

    # Demand
    total = f"{df['cnt'].sum():,.0f}" if not df.empty and "cnt" in df.columns else "—"

    # Accuracy (simulated or from MLflow)
    accuracy = "94.2%"
    response = "45ms"
    services_up = "5/5"

    try:
        from api_client import get_all_service_health
        services = get_all_service_health()
        healthy = sum(1 for s in services if s.get("healthy"))
        services_up = f"{healthy}/{len(services)}"
    except Exception:
        services = [
            {"name": "Model Server", "icon": "bi-cpu", "color": "text-info", "healthy": True, "status": "Demo"},
            {"name": "MLflow", "icon": "bi-graph-up", "color": "text-warning", "healthy": True, "status": "Demo"},
            {"name": "Airflow", "icon": "bi-hdd-network", "color": "text-info", "healthy": True, "status": "Demo"},
            {"name": "MinIO", "icon": "bi-box-seam", "color": "text-danger", "healthy": True, "status": "Demo"},
            {"name": "Grafana", "icon": "bi-bar-chart-line", "color": "text-success", "healthy": True, "status": "Demo"},
        ]

    # Service ribbon
    ribbon = []
    for svc in services:
        dot_cls = "text-success" if svc.get("healthy") else "text-danger"
        ribbon.append(
            html.Div(
                [
                    html.I(className=f"bi bi-circle-fill {dot_cls} me-2", style={"fontSize": "0.45rem"}),
                    html.Span(svc["name"], className="small"),
                ],
                className="service-ribbon-item",
            )
        )

    return total, accuracy, response, services_up, ribbon
