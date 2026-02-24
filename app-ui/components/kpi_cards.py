"""Reusable KPI card components for the UrbanFlow dashboard."""

import dash_bootstrap_components as dbc
from dash import html


def create_kpi_card(id_prefix, title, icon_class, color_class, icon_bg_class):
    """Premium KPI card with accent glow border and icon pill."""
    return dbc.Col(
        html.Div(
            [
                html.Div(
                    [
                        html.Div(
                            [html.I(className=f"bi {icon_class}")],
                            className=f"section-icon {icon_bg_class}",
                        ),
                        html.H6(
                            title,
                            className="kpi-label mb-0 ms-2 d-none d-md-block",
                        ),
                    ],
                    className="d-flex align-items-center",
                ),
                html.H3("—", id=f"{id_prefix}-value", className="kpi-value"),
                html.Div(
                    [
                        html.Span(id=f"{id_prefix}-trend", className="badge"),
                        html.Span(
                            " vs prev.",
                            className="text-muted ms-2 small d-none d-lg-inline",
                        ),
                    ],
                    className="kpi-trend",
                ),
            ],
            className=f"glass-card border-top-{color_class} h-100",
        ),
        width=6,
        lg=3,
        className="mb-4",
    )
