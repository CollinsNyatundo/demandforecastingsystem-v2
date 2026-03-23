"""Top navbar component for the UrbanFlow dashboard."""

from dash import html

from config_theme import THEME


def create_navbar():
    """Build the top navigation bar with brand, badges, and animated bike SVG."""
    return html.Nav(
        html.Div(
            [
                # Left: Brand title
                html.Div(
                    [
                        html.I(
                            className="bi bi-graph-up-arrow me-2",
                            style={"color": THEME["blue"], "fontSize": "1.2rem"},
                        ),
                        html.Span("URBAN", className="text-white fw-bold"),
                        html.Span(
                            "FLOW",
                            style={"color": THEME["blue"], "fontWeight": 300},
                        ),
                        html.Span(
                            " Intelligence",
                            className="text-muted fw-light d-none d-md-inline ms-1",
                            style={"fontSize": "0.8rem"},
                        ),
                        # Animated Bike — uses html.Img for cross-version compatibility
                        html.Img(
                            src="/assets/animated_bike.svg",
                            alt="UrbanFlow Bike",
                            style={
                                "height": "32px",
                                "marginLeft": "12px",
                                "animation": "slide-in-right 2s ease-out",
                            },
                            className="d-none d-lg-inline",
                        ),
                    ],
                    className="d-flex align-items-center",
                ),
                # Right: Status badges
                html.Div(
                    [
                        html.Span(
                            [html.I(className="bi bi-circle-fill me-1", style={"fontSize": "0.5rem"}), "Live"],
                            className="badge badge-cyan me-2",
                        ),
                        html.Span(
                            [html.I(className="bi bi-gear me-1", style={"fontSize": "0.65rem"}), "Pipeline"],
                            className="badge badge-success",
                        ),
                    ],
                    className="d-flex align-items-center",
                ),
            ],
            className="navbar-inner",
        ),
        className="top-navbar",
    )
