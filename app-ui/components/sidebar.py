"""Persistent sidebar navigation component for the UrbanFlow dashboard."""

import dash_bootstrap_components as dbc
from dash import html

from config_theme import THEME


def create_sidebar():
    """Build the collapsible sidebar with navigation links and status."""
    nav_items = [
        {"label": "Home", "icon": "bi bi-house-door", "href": "/"},
        {"label": "Dashboard", "icon": "bi bi-speedometer2", "href": "/dashboard"},
        {
            "label": "Predictions",
            "icon": "bi bi-lightning-charge",
            "href": "/predictions",
        },
        {
            "label": "Model Health",
            "icon": "bi bi-heart-pulse",
            "href": "/model-metrics",
        },
    ]

    external_links = [
        {
            "label": "MLflow",
            "icon": "bi bi-graph-up",
            "href": "http://localhost:5000",
            "external": True,
        },
        {
            "label": "Airflow",
            "icon": "bi bi-hdd-network",
            "href": "http://localhost:8081",
            "external": True,
        },
        {
            "label": "Grafana",
            "icon": "bi bi-bar-chart-line",
            "href": "http://localhost:3000",
            "external": True,
        },
        {
            "label": "MinIO",
            "icon": "bi bi-box-seam",
            "href": "http://localhost:9001",
            "external": True,
        },
        {
            "label": "Prometheus",
            "icon": "bi bi-activity",
            "href": "http://localhost:9090",
            "external": True,
        },
        {
            "label": "Optuna",
            "icon": "bi bi-speedometer2",
            "href": "http://localhost:8084",
            "external": True,
        },
        {
            "label": "ClearML",
            "icon": "bi bi-broadcast",
            "href": "http://localhost:8082",
            "external": True,
        },
        {
            "label": "Nginx Status",
            "icon": "bi bi-diagram-2",
            "href": "http://localhost:8888/nginx_status",
            "external": True,
        },
    ]

    nav_links = []
    for item in nav_items:
        nav_links.append(
            dbc.NavLink(
                [
                    html.I(className=f"{item['icon']} me-3"),
                    html.Span(item["label"]),
                ],
                href=item["href"],
                className="sidebar-link",
                active="exact",
            )
        )

    ext_links = []
    for item in external_links:
        ext_links.append(
            html.A(
                [
                    html.I(className=f"{item['icon']} me-3"),
                    html.Span(item["label"]),
                    html.I(
                        className="bi bi-box-arrow-up-right ms-auto",
                        style={"fontSize": "0.7rem"},
                    ),
                ],
                href=item["href"],
                target="_blank",
                rel="noopener noreferrer",
                className="sidebar-link sidebar-external",
            )
        )

    return html.Aside(
        [
            # Brand
            html.Div(
                [
                    html.Img(
                        src="/assets/animated_bike.svg",
                        style={"height": "36px"},
                        className="me-2",
                    ),
                    html.Div(
                        [
                            html.Span(
                                "URBAN",
                                className="text-white fw-bold",
                                style={"fontSize": "0.9rem"},
                            ),
                            html.Span(
                                "FLOW",
                                style={
                                    "color": THEME["blue"],
                                    "fontWeight": 300,
                                    "fontSize": "0.9rem",
                                },
                            ),
                        ],
                    ),
                ],
                className="sidebar-brand",
            ),
            html.Hr(className="sidebar-divider"),
            # Navigation
            html.Div(
                [
                    html.Small("NAVIGATION", className="sidebar-section-label"),
                    dbc.Nav(nav_links, vertical=True, pills=True),
                ],
                className="mb-4",
            ),
            # External Services
            html.Div(
                [
                    html.Small("SERVICES", className="sidebar-section-label"),
                    html.Div(ext_links),
                ],
                className="mb-4",
            ),
            # System Status (bottom)
            html.Div(
                [
                    html.Hr(className="sidebar-divider"),
                    html.Div(
                        [
                            html.Div(className="status-dot-live"),
                            html.Small(
                                "System Operational", className="text-muted ms-2"
                            ),
                        ],
                        className="d-flex align-items-center px-3 py-2",
                    ),
                ],
                className="mt-auto",
            ),
        ],
        className="sidebar",
        id="sidebar",
    )
