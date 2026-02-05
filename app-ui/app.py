"""
Demand Forecasting Dashboard - Production-ready Dash application.

Provides interactive visualization of bike demand data with filtering
by date range and season. Includes health check endpoint for orchestration.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Input, Output, callback, dcc, html
from flask import jsonify

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Setup paths - avoid changing working directory in production
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "app-ml" / "src"))

from common.utils import read_config


class DataLoadError(Exception):
    """Raised when data loading fails."""

    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""

    pass


# Application state
app_state = {
    "data_loaded": False,
    "startup_time": datetime.utcnow().isoformat(),
    "error": None,
}

# Load Configuration
try:
    config_path = project_root / "config" / "config.yaml"
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    config = read_config(config_path)
    logger.info(f"Configuration loaded from {config_path}")
except Exception as e:
    logger.error(f"Failed to load configuration: {e}")
    app_state["error"] = str(e)
    config = {}

# Load Data with proper error handling
df = pd.DataFrame()
season_map = {1: "Spring", 2: "Summer", 3: "Fall", 4: "Winter"}

try:
    if "data_manager" not in config:
        raise ConfigurationError("Missing 'data_manager' in configuration")

    data_path = project_root / config["data_manager"]["raw_data_path"]
    if not data_path.exists():
        raise DataLoadError(f"Data file not found: {data_path}")

    logger.info(f"Loading data from {data_path}")
    df = pd.read_parquet(data_path)

    # Validate required columns
    required_columns = {"datetime", "cnt", "temp", "registered", "season"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise DataLoadError(f"Missing required columns: {missing_columns}")

    # Preprocessing
    df["datetime"] = pd.to_datetime(df["datetime"])
    df["date"] = df["datetime"].dt.date
    df["season_label"] = df["season"].map(season_map)

    # Global KPIs (computed once)
    total_demand_all = df["cnt"].sum()
    avg_temp_all = df["temp"].mean()
    total_registered_all = df["registered"].sum()

    app_state["data_loaded"] = True
    app_state["row_count"] = len(df)
    logger.info(f"Data loaded successfully: {len(df)} rows")

except DataLoadError as e:
    logger.error(f"Data loading failed: {e}")
    app_state["error"] = str(e)
    app_state["data_loaded"] = False
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    app_state["error"] = str(e)
    app_state["data_loaded"] = False
except Exception as e:
    logger.exception(f"Unexpected error during data loading: {e}")
    app_state["error"] = f"Unexpected error: {e}"
    app_state["data_loaded"] = False

# Initialize App with LUMEN theme (Professional/Light)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUMEN, dbc.icons.BOOTSTRAP])
server = app.server
app.title = "Demand Forecasting"


# ============================================
# Health & Readiness Endpoints for Orchestration
# ============================================
@server.route("/health")
def health_check():
    """
    Basic health check endpoint for load balancers.

    Returns 200 if the service is running.
    """
    return jsonify(
        {
            "status": "healthy",
            "service": "demand-forecasting-ui",
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


@server.route("/ready")
def readiness_check():
    """
    Readiness probe for Kubernetes/orchestration.

    Returns 200 only if the application is ready to serve traffic:
    - Data is loaded
    - No critical errors
    """
    is_ready = app_state["data_loaded"] and app_state["error"] is None

    response = {
        "ready": is_ready,
        "checks": {
            "data_loaded": app_state["data_loaded"],
            "no_errors": app_state["error"] is None,
        },
        "startup_time": app_state["startup_time"],
        "timestamp": datetime.utcnow().isoformat(),
    }

    if not is_ready:
        response["error"] = app_state.get("error")

    status_code = 200 if is_ready else 503
    return jsonify(response), status_code


@server.route("/metrics")
def metrics():
    """
    Basic metrics endpoint for monitoring.

    Returns application metrics in JSON format.
    """
    return jsonify(
        {
            "service": "demand-forecasting-ui",
            "data_loaded": app_state["data_loaded"],
            "row_count": app_state.get("row_count", 0),
            "startup_time": app_state["startup_time"],
            "uptime_seconds": (
                datetime.utcnow()
                - datetime.fromisoformat(app_state["startup_time"])
            ).total_seconds(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


# Helper function for chart styling
def style_figure(fig):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#455A64"),  # Slate text
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0"),
        margin=dict(l=40, r=20, t=40, b=40),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Segoe UI"),
    )
    return fig


def create_error_layout(error_message: str) -> html.Div:
    """Create error display layout when data fails to load."""
    return html.Div(
        [
            dbc.NavbarSimple(
                brand="Demand Forecasting System",
                brand_href="#",
                color="transparent",
                dark=False,
                fluid=True,
                className="custom-navbar mb-4",
            ),
            dbc.Container(
                [
                    dbc.Alert(
                        [
                            html.H4("Data Loading Error", className="alert-heading"),
                            html.P(f"Failed to load data: {error_message}"),
                            html.Hr(),
                            html.P(
                                "Please check the data files and configuration.",
                                className="mb-0",
                            ),
                        ],
                        color="danger",
                        className="mt-5",
                    ),
                ],
                fluid=True,
            ),
        ]
    )


def create_dashboard_layout() -> html.Div:
    """Create the main dashboard layout."""
    # Handle empty dataframe gracefully
    if df.empty:
        min_date = datetime.now().date()
        max_date = datetime.now().date()
    else:
        min_date = df["date"].min()
        max_date = df["date"].max()

    return html.Div(
        [
            # Navbar
            dbc.NavbarSimple(
                brand="Demand Forecasting System",
                brand_href="#",
                color="transparent",
                dark=False,
                fluid=True,
                className="custom-navbar mb-4",
            ),
            dbc.Container(
                [
                    # Hero Section
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H1("URBAN FLOW CYCLING", className="hero-title"),
                                    html.P(
                                        "Smart Demand Forecasting & Mobility Analytics",
                                        className="hero-subtitle",
                                    ),
                                ],
                                className="hero-overlay",
                            )
                        ],
                        className="hero-container",
                    ),
                    # Filter Row
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label(
                                        "Select Date Range", className="fw-bold text-slate"
                                    ),
                                    dcc.DatePickerRange(
                                        id="date-picker-range",
                                        min_date_allowed=min_date,
                                        max_date_allowed=max_date,
                                        start_date=min_date,
                                        end_date=max_date,
                                        className="mb-2 d-block",
                                    ),
                                ],
                                width=12,
                                md=6,
                            ),
                            dbc.Col(
                                [
                                    html.Label(
                                        "Select Seasons", className="fw-bold text-slate"
                                    ),
                                    dcc.Dropdown(
                                        id="season-dropdown",
                                        options=[
                                            {"label": s, "value": s}
                                            for s in season_map.values()
                                        ],
                                        value=list(season_map.values()),
                                        multi=True,
                                        clearable=False,
                                    ),
                                ],
                                width=12,
                                md=6,
                            ),
                        ],
                        className="mb-4",
                    ),
                    # KPI Row
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Total Rentals"),
                                        dbc.CardBody(
                                            html.H3(
                                                id="kpi-demand", className="text-forest"
                                            )
                                        ),
                                    ],
                                    className="pro-card mb-4",
                                ),
                                width=12,
                                md=4,
                            ),
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Avg. Temp (Norm)"),
                                        dbc.CardBody(
                                            html.H3(
                                                id="kpi-temp", className="text-science-blue"
                                            )
                                        ),
                                    ],
                                    className="pro-card mb-4",
                                ),
                                width=12,
                                md=4,
                            ),
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Registered Users"),
                                        dbc.CardBody(
                                            html.H3(id="kpi-users", className="text-slate")
                                        ),
                                    ],
                                    className="pro-card mb-4",
                                ),
                                width=12,
                                md=4,
                            ),
                        ]
                    ),
                    # Charts
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Daily Demand Trends"),
                                        dbc.CardBody(
                                            dcc.Graph(
                                                id="fig-demand",
                                                config={"displayModeBar": "hover"},
                                            )
                                        ),
                                    ],
                                    className="pro-card mb-4",
                                ),
                                width=12,
                            ),
                        ]
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Seasonality Distribution"),
                                        dbc.CardBody(
                                            dcc.Graph(
                                                id="fig-seasonality",
                                                config={"displayModeBar": "hover"},
                                            )
                                        ),
                                    ],
                                    className="pro-card mb-4",
                                ),
                                width=12,
                                lg=6,
                            ),
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader("Temperature Impact"),
                                        dbc.CardBody(
                                            dcc.Graph(
                                                id="fig-corr",
                                                config={"displayModeBar": "hover"},
                                            )
                                        ),
                                    ],
                                    className="pro-card mb-4",
                                ),
                                width=12,
                                lg=6,
                            ),
                        ]
                    ),
                ],
                fluid=True,
            ),
        ]
    )


# Set the layout based on data loading state
if app_state["data_loaded"]:
    app.layout = create_dashboard_layout()
else:
    app.layout = create_error_layout(app_state.get("error", "Unknown error"))


@callback(
    [
        Output("kpi-demand", "children"),
        Output("kpi-temp", "children"),
        Output("kpi-users", "children"),
        Output("fig-demand", "figure"),
        Output("fig-seasonality", "figure"),
        Output("fig-corr", "figure"),
    ],
    [
        Input("date-picker-range", "start_date"),
        Input("date-picker-range", "end_date"),
        Input("season-dropdown", "value"),
    ],
)
def update_dashboard(start_date, end_date, selected_seasons):
    """
    Update dashboard components based on filter selections.

    Args:
        start_date: Start date for filtering
        end_date: End date for filtering
        selected_seasons: List of selected seasons

    Returns:
        Tuple of KPI values and figures
    """
    # Handle empty dataframe
    if df.empty:
        logger.warning("Dashboard update called with empty dataframe")
        empty_fig = px.line(title="No Data Available")
        empty_fig = style_figure(empty_fig)
        return "N/A", "N/A", "N/A", empty_fig, empty_fig, empty_fig

    try:
        # Filter Data
        mask = (
            (df["date"] >= pd.to_datetime(start_date).date())
            & (df["date"] <= pd.to_datetime(end_date).date())
            & (df["season_label"].isin(selected_seasons))
        )
        filtered_df = df.loc[mask]

        # Handle empty filter results
        if filtered_df.empty:
            logger.info("Filter returned no results")
            empty_fig = px.line(title="No Data for Selected Filters")
            empty_fig = style_figure(empty_fig)
            return "0", "N/A", "0", empty_fig, empty_fig, empty_fig

        # Recalculate KPIs
        k_demand = filtered_df["cnt"].sum()
        k_temp = filtered_df["temp"].mean()
        k_users = filtered_df["registered"].sum()

        # 1. Daily Trend
        daily_data = filtered_df.groupby("date")["cnt"].sum().reset_index()
        fig1 = px.line(daily_data, x="date", y="cnt", title=None)
        fig1.update_traces(line_color="#2E7D32", line_width=3)  # Forest Green
        fig1 = style_figure(fig1)

        # 2. Seasonality
        # Eco-friendly palette: Green, Gold, Orange, Blue
        season_colors = {
            "Spring": "#66BB6A",
            "Summer": "#FDD835",
            "Fall": "#FF7043",
            "Winter": "#42A5F5",
        }
        fig2 = px.box(
            filtered_df,
            x="season_label",
            y="cnt",
            color="season_label",
            category_orders={"season_label": ["Spring", "Summer", "Fall", "Winter"]},
            color_discrete_map=season_colors,
        )
        fig2.update_layout(showlegend=False)
        fig2 = style_figure(fig2)

        # 3. Correlation
        # Sample down if too large
        plot_df = filtered_df if len(filtered_df) < 5000 else filtered_df.sample(5000)
        fig3 = px.scatter(
            plot_df,
            x="temp",
            y="cnt",
            color="season_label",
            opacity=0.6,
            color_discrete_map=season_colors,
        )
        fig3 = style_figure(fig3)

        logger.debug(f"Dashboard updated: {len(filtered_df)} rows filtered")
        return f"{k_demand:,.0f}", f"{k_temp:.2f}", f"{k_users:,.0f}", fig1, fig2, fig3

    except Exception as e:
        logger.exception(f"Error updating dashboard: {e}")
        error_fig = px.line(title="Error Loading Data")
        error_fig = style_figure(error_fig)
        return "Error", "Error", "Error", error_fig, error_fig, error_fig


if __name__ == "__main__":
    logger.info(
        f"Starting Demand Forecasting UI - "
        f"Data loaded: {app_state['data_loaded']}, "
        f"Rows: {app_state.get('row_count', 0)}"
    )
    app.run(debug=True, use_reloader=False, host="0.0.0.0", port=8050)
