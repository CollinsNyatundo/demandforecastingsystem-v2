"""Dashboard page — Primary operational view for ML engineers."""

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from components.kpi_cards import create_kpi_card
from config_theme import PLOTLY_DEFAULTS, THEME

dash.register_page(__name__, path="/dashboard", name="Dashboard", order=1)


# Pre-styled empty figure — rendered on first paint so charts start dark,
# not white. Eliminates the flash-of-unstyled-content (FOUC) on page load.
def _empty_fig(height=360):
    fig = go.Figure()
    fig.update_layout(
        **{
            **PLOTLY_DEFAULTS,
            "height": height,
            "xaxis": {"visible": False},
            "yaxis": {"visible": False},
            "annotations": [
                {
                    "text": "",
                    "showarrow": False,
                }
            ],
        }
    )
    return fig


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
layout = html.Div(
    [
        # --- Modals ---
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Trigger Retraining Pipeline")),
                dbc.ModalBody(id="retrain-modal-body"),
                dbc.ModalFooter(
                    dbc.Button(
                        "Close",
                        id="btn-close-retrain-modal",
                        className="ms-auto",
                        n_clicks=0,
                    )
                ),
            ],
            id="retrain-modal",
            is_open=False,
            centered=True,
        ),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Evidently Data Drift Report")),
                dbc.ModalBody(
                    html.Iframe(
                        id="drift-report-iframe",
                        style={"width": "100%", "height": "75vh", "border": "none"},
                    ),
                    className="p-0",
                ),
            ],
            id="drift-modal",
            is_open=False,
            size="xl",
            centered=True,
        ),
        dcc.Interval(id="dash-interval", interval=60000, n_intervals=0),
        dcc.Store(id="active-chart-tab", data="demand"),
        dcc.Store(
            id="latest-drift-report", data=""
        ),  # Store for the latest drift report name
        # Page header
        html.Div(
            [
                html.Div(
                    [
                        html.H4("Operational Dashboard", className="page-title"),
                        html.P(
                            "Real-time demand predictions powering fleet optimization. "
                            "The model processes weather, temporal, and historical patterns "
                            "to forecast ridership.",
                            className="page-description",
                        ),
                    ],
                ),
            ],
            className="page-header mb-4",
        ),
        # Drift Alert Banner
        html.Div(id="dash-drift-alert"),
        # Filters
        dbc.Row(
            [
                dbc.Col(
                    [
                        html.Label("Season Filter", className="filter-label"),
                        dcc.Dropdown(
                            id="dash-season",
                            options=[
                                {"label": s, "value": s.lower()}
                                for s in ["Spring", "Summer", "Fall", "Winter"]
                            ],
                            value=["spring", "summer", "fall", "winter"],
                            multi=True,
                            clearable=False,
                            persistence=True,
                            persistence_type="session",
                            className="dropdown-custom",
                        ),
                    ],
                    md=4,
                    className="mb-3",
                ),
                dbc.Col(
                    [
                        html.Label("Date Range", className="filter-label"),
                        dcc.DatePickerRange(
                            id="dash-daterange",
                            display_format="MM/DD/YYYY",
                            persistence=True,
                            persistence_type="session",
                            className="date-picker-custom",
                        ),
                    ],
                    md=5,
                    className="mb-3",
                ),
            ],
            className="mb-4",
        ),
        # KPI Row
        dbc.Row(
            [
                create_kpi_card(
                    "kpi-total",
                    "TOTAL PREDICTIONS",
                    "bi-calculator",
                    "cyan",
                    "bg-cyan-subtle",
                ),
                create_kpi_card(
                    "kpi-accuracy",
                    "MODEL ACCURACY",
                    "bi-bullseye",
                    "green",
                    "bg-green-subtle",
                ),
                create_kpi_card(
                    "kpi-response",
                    "AVG RESPONSE",
                    "bi-clock",
                    "purple",
                    "bg-purple-subtle",
                ),
                create_kpi_card(
                    "kpi-active",
                    "ACTIVE SESSIONS",
                    "bi-people",
                    "amber",
                    "bg-amber-subtle",
                ),
            ],
        ),
        # Charts Row
        dbc.Row(
            [
                # Main Forecast Chart
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.I(
                                                className="bi bi-graph-up me-2",
                                                style={"color": THEME["blue"]},
                                            ),
                                            html.H6(
                                                id="main-forecast-chart-title",
                                                className="mb-0 text-white",
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                    ),
                                    html.Div(
                                        [
                                            html.Button(
                                                "Demand",
                                                id="tab-demand",
                                                className="chart-tab-btn active",
                                                n_clicks=0,
                                            ),
                                            html.Button(
                                                "Hourly Pattern",
                                                id="tab-hourly",
                                                className="chart-tab-btn",
                                                n_clicks=0,
                                            ),
                                            html.Button(
                                                "Weekly Heatmap",
                                                id="tab-weekly",
                                                className="chart-tab-btn",
                                                n_clicks=0,
                                            ),
                                        ],
                                        className="chart-tabs",
                                    ),
                                ],
                                className="d-flex justify-content-between align-items-center mb-3",
                            ),
                            dcc.Loading(
                                type="dot",
                                color=THEME["blue"],
                                children=dcc.Graph(
                                    id="main-forecast-chart",
                                    figure=_empty_fig(360),
                                    config={"displayModeBar": False},
                                    style={"height": "360px"},
                                ),
                            ),
                        ],
                        className="glass-panel p-4 h-100",
                    ),
                    width=12,
                    lg=8,
                ),
                # Right Column — Gauge + Feature Importance + Model Metrics
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="bi bi-speedometer me-2",
                                        style={"color": THEME["green"]},
                                    ),
                                    html.H6(
                                        "Model Performance", className="mb-0 text-white"
                                    ),
                                ],
                                className="d-flex align-items-center mb-3",
                            ),
                            dcc.Graph(
                                id="confidence-gauge",
                                figure=_empty_fig(140),
                                config={"displayModeBar": False},
                                style={"height": "140px"},
                            ),
                            html.H6(
                                "FEATURE IMPORTANCE",
                                className="mb-2",
                                style={
                                    "color": THEME["text_secondary"],
                                    "fontSize": "0.75rem",
                                    "fontWeight": 600,
                                    "textTransform": "uppercase",
                                    "letterSpacing": "0.06em",
                                },
                            ),
                            dcc.Graph(
                                id="feature-importance-chart",
                                figure=_empty_fig(150),
                                config={"displayModeBar": False},
                                style={"height": "150px"},
                            ),
                            html.Hr(className="section-divider my-3"),
                            html.Div(id="model-metrics-container"),
                        ],
                        className="glass-panel p-4 h-100",
                    ),
                    width=12,
                    lg=4,
                ),
            ],
            className="mb-4",
        ),
        # Bottom Row — Predictions Table + System Health
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="bi bi-table me-2",
                                        style={"color": THEME["blue"]},
                                    ),
                                    html.H6(
                                        "Recent Predictions",
                                        className="mb-0 text-white",
                                    ),
                                ],
                                className="d-flex align-items-center mb-3",
                            ),
                            html.Div(id="table-container"),
                        ],
                        className="glass-panel p-4",
                    ),
                    width=12,
                    lg=8,
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(
                                        className="bi bi-heart-pulse me-2",
                                        style={"color": THEME["rose"]},
                                    ),
                                    html.H6(
                                        "System Health", className="mb-0 text-white"
                                    ),
                                ],
                                className="d-flex align-items-center mb-3",
                            ),
                            html.Div(id="system-health-container"),
                        ],
                        className="glass-panel p-4",
                    ),
                    width=12,
                    lg=4,
                ),
            ],
        ),
    ],
    className="page-dashboard",
)


# ---------------------------------------------------------------------------
# Tab-switch callback — updates active CSS class and stores selected tab
# ---------------------------------------------------------------------------
@callback(
    Output("active-chart-tab", "data"),
    Output("tab-demand", "className"),
    Output("tab-hourly", "className"),
    Output("tab-weekly", "className"),
    Input("tab-demand", "n_clicks"),
    Input("tab-hourly", "n_clicks"),
    Input("tab-weekly", "n_clicks"),
    prevent_initial_call=True,
)
def update_tabs(n_demand, n_hourly, n_weekly):
    from dash import ctx

    trigger = ctx.triggered_id or "tab-demand"
    if trigger == "tab-hourly":
        return "hourly", "chart-tab-btn", "chart-tab-btn active", "chart-tab-btn"
    elif trigger == "tab-weekly":
        return "weekly", "chart-tab-btn", "chart-tab-btn", "chart-tab-btn active"

    return "demand", "chart-tab-btn active", "chart-tab-btn", "chart-tab-btn"


@callback(
    Output("retrain-modal", "is_open"),
    Output("retrain-modal-body", "children"),
    Input("btn-trigger-retrain", "n_clicks"),
    Input("btn-close-retrain-modal", "n_clicks"),
    State("retrain-modal", "is_open"),
    prevent_initial_call=True,
)
def handle_retrain_trigger(n_open, n_close, is_open):
    from dash import ctx

    trigger = ctx.triggered_id

    if trigger == "btn-trigger-retrain":
        try:
            from api_client import trigger_airflow_dag

            result = trigger_airflow_dag("demand_forecasting_enhanced")
            if result.get("success"):
                msg = html.Div(
                    [
                        html.I(
                            className="bi bi-check-circle-fill text-success fs-2 d-block text-center mb-3"
                        ),
                        html.P(
                            "Retraining pipeline has been successfully triggered in Airflow.",
                            className="text-center",
                        ),
                    ]
                )
            else:
                msg = html.Div(
                    [
                        html.I(
                            className="bi bi-x-circle-fill text-danger fs-2 d-block text-center mb-3"
                        ),
                        html.P(
                            f"Failed to trigger DAG: {result.get('error')}",
                            className="text-center text-danger",
                        ),
                    ]
                )
        except Exception as e:
            msg = html.P(f"Error: {e}", className="text-danger")
        return True, msg

    if trigger == "btn-close-retrain-modal":
        return False, dash.no_update

    return dash.no_update, dash.no_update


@callback(
    Output("drift-modal", "is_open"),
    Output("drift-report-iframe", "src"),
    Input("btn-view-drift-report", "n_clicks"),
    State("latest-drift-report", "data"),
    prevent_initial_call=True,
)
def handle_drift_modal(n_clicks, report_name):
    if n_clicks and report_name:
        return True, f"/reports/{report_name}"
    return dash.no_update, dash.no_update


# ---------------------------------------------------------------------------
# Main dashboard callback
# ---------------------------------------------------------------------------
@callback(
    [
        Output("kpi-total-value", "children"),
        Output("kpi-total-trend", "children"),
        Output("kpi-accuracy-value", "children"),
        Output("kpi-accuracy-trend", "children"),
        Output("kpi-response-value", "children"),
        Output("kpi-response-trend", "children"),
        Output("kpi-active-value", "children"),
        Output("kpi-active-trend", "children"),
        Output("main-forecast-chart", "figure"),
        Output("main-forecast-chart-title", "children"),  # New output for chart title
        Output("confidence-gauge", "figure"),
        Output("feature-importance-chart", "figure"),
        Output("table-container", "children"),
        Output("system-health-container", "children"),
        Output("dash-drift-alert", "children"),
        Output("model-metrics-container", "children"),
        Output(
            "latest-drift-report", "data"
        ),  # New output for latest drift report name
    ],
    [
        Input("dash-daterange", "start_date"),
        Input("dash-daterange", "end_date"),
        Input("dash-season", "value"),
        Input("dash-interval", "n_intervals"),
        Input("active-chart-tab", "data"),
    ],
)
def update_dashboard(start_date, end_date, seasons, n_intervals, active_tab):

    from config_theme import df

    # --- Input Validation ---
    if not seasons:
        seasons = ["spring", "summer", "fall", "winter"]
    if start_date and end_date and start_date > end_date:
        start_date, end_date = None, None

    active_tab = active_tab or "demand"

    # --- API imports ---
    mlflow_run = None
    services = []
    drift_metrics = {}
    prom_metrics = {}
    fi_data = {}
    latest_report_name = None
    try:
        from api_client import (
            get_all_service_health,
            get_best_mlflow_run,
            get_drift_metrics,
            get_feature_importance,
            get_latest_drift_report_name,
            get_prometheus_metrics,
        )

        mlflow_run = get_best_mlflow_run()  # Best run by RMSE
        services = get_all_service_health()
        drift_metrics = get_drift_metrics()
        prom_metrics = get_prometheus_metrics()
        fi_data = get_feature_importance()
        latest_report_name = get_latest_drift_report_name()
    except Exception:
        services = [
            {
                "name": n,
                "icon": i,
                "color": c,
                "healthy": True,
                "status": "Demo",
                "detail": "Simulated",
            }
            for n, i, c in [
                ("Model Server", "bi-cpu", "text-info"),
                ("MLflow", "bi-graph-up", "text-warning"),
                ("Airflow", "bi-hdd-network", "text-info"),
                ("MinIO", "bi-box-seam", "text-danger"),
                ("Grafana", "bi-bar-chart-line", "text-success"),
            ]
        ]

    # --- Data Filtering ---
    if df.empty or "cnt" not in df.columns:
        filtered = pd.DataFrame()
        total_demand = 12_400_000
    else:
        mask = pd.Series(True, index=df.index)
        if start_date:
            mask &= df["date"] >= pd.to_datetime(start_date).date()
        if end_date:
            mask &= df["date"] <= pd.to_datetime(end_date).date()
        if seasons:
            mask &= df["season_label"].isin(seasons)
        filtered = df[mask].copy()
        total_demand = filtered["cnt"].sum() if not filtered.empty else 0

    # --- KPIs ---
    kpi_total = prom_metrics.get("total_predictions", total_demand)
    kpi_total_val = f"{kpi_total:,.0f}"
    kpi_total_trend = html.Span(
        [html.I(className="bi bi-arrow-up-right me-1"), "Live"],
        className="badge badge-success",
    )

    accuracy = (mlflow_run or {}).get("mape", 5.8)
    acc_val = f"{100 - float(accuracy):.1f}%" if accuracy else "94.2%"
    kpi_acc_val = acc_val
    kpi_acc_trend = html.Span(
        [html.I(className="bi bi-arrow-up-right me-1"), "Tracked"],
        className="badge badge-success",
    )

    latency = prom_metrics.get("avg_latency_ms", 0)
    kpi_resp_val = f"{latency}ms" if latency else f"{45}ms"
    kpi_resp_trend = html.Span(
        [html.I(className="bi bi-arrow-down-right me-1"), "Live"],
        className="badge badge-success",
    )

    active = prom_metrics.get("active_sessions", 42)
    kpi_active_val = f"{active}"
    kpi_active_trend = html.Span(
        [html.I(className="bi bi-dash me-1"), "Est."], className="badge badge-muted"
    )

    # --- Forecast / Hourly Pattern / Weekly Heatmap / XAI ---
    fig_main = go.Figure()
    chart_title = "Demand Forecast & Actuals"

    if active_tab == "hourly":
        chart_title = "Average Hourly Demand Pattern"
        if not filtered.empty:
            hour_avg = filtered.groupby("hour")["cnt"].mean().reset_index()
            fig_main.add_trace(
                go.Bar(
                    x=hour_avg["hour"],
                    y=hour_avg["cnt"],
                    marker_color=THEME["blue"],
                    name="Average Demand",
                )
            )
            fig_main.update_layout(
                **{
                    **PLOTLY_DEFAULTS,
                    "xaxis": {"title": "Hour of Day", "tickmode": "linear", "dtick": 2},
                    "yaxis": {"title": "Average Demand"},
                }
            )
    elif active_tab == "weekly":
        chart_title = "Weekly Demand Heatmap"
        if not filtered.empty:
            # Weekly heatmap: hour × day_of_week grid
            pivot = (
                filtered.pivot_table(
                    values="cnt",
                    index="hour",
                    columns="dteday_dayofweek",
                    aggfunc="mean",
                )
                if "dteday_dayofweek" in filtered.columns
                else filtered.pivot_table(
                    values="cnt",
                    index="hour",
                    columns=filtered["datetime"].dt.dayofweek
                    if "datetime" in filtered.columns
                    else filtered.index,
                    aggfunc="mean",
                )
            )
            day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            cols = [
                day_labels[int(c) % 7] if isinstance(c, (int, float)) else str(c)
                for c in pivot.columns
            ]
            fig_main.add_trace(
                go.Heatmap(
                    z=pivot.values,
                    x=cols,
                    y=list(pivot.index),
                    colorscale=[
                        [0, "#0d1117"],
                        [0.5, THEME["blue"]],
                        [1, THEME["cyan"]],
                    ],
                    showscale=True,
                    colorbar={
                        "thickness": 8,
                        "len": 0.8,
                        "tickfont": {"color": THEME["text_secondary"], "size": 9},
                    },
                )
            )
            fig_main.update_layout(
                **{
                    **PLOTLY_DEFAULTS,
                    "xaxis": {"title": "Day of Week"},
                    "yaxis": {"title": "Hour", "dtick": 4},
                }
            )
        else:
            # Default: demand time series
            chart = filtered.tail(200)
            last_date = pd.to_datetime(chart["datetime"].max())

            futures = []
            if not chart.empty:
                try:
                    from api_client import send_prediction

                    last_row = chart.iloc[-1]
                    base_time = pd.to_datetime(last_row["datetime"])

                    for i in range(1, 4):
                        next_time = base_time + pd.Timedelta(hours=i)
                        features = {
                            "temp": float(last_row.get("temp", 0.5)),
                            "humidity": float(last_row.get("hum", 0.5)),
                            "wind_speed": float(last_row.get("windspeed", 0.1)),
                            "hour": next_time.hour,
                            "day_of_week": next_time.dayofweek,
                            "month": next_time.month,
                        }
                        res = send_prediction(features)
                        pred = res.get("prediction", chart["cnt"].mean())
                        futures.append({"datetime": next_time, "cnt": pred})
                except Exception:
                    # Fallback on failure
                    for i in range(1, 4):
                        futures.append(
                            {
                                "datetime": last_date + pd.Timedelta(hours=i),
                                "cnt": chart["cnt"].mean(),
                            }
                        )

            chart = pd.concat([chart, pd.DataFrame(futures)])
            fig_main.add_trace(
                go.Scatter(
                    x=chart["datetime"],
                    y=chart["cnt"],
                    mode="lines",
                    fill="tozeroy",
                    fillcolor="rgba(59,130,246,0.08)",
                    line={"color": THEME["blue"], "width": 2},
                    name="Demand",
                )
            )
            fig_main.update_layout(**PLOTLY_DEFAULTS)
    else:  # active_tab == "demand"
        chart_title = "Demand Forecast & Actuals"
        chart = filtered.tail(200)
        last_date = pd.to_datetime(chart["datetime"].max())

        futures = []
        if not chart.empty:
            try:
                from api_client import send_prediction

                last_row = chart.iloc[-1]
                base_time = pd.to_datetime(last_row["datetime"])

                for i in range(1, 4):
                    next_time = base_time + pd.Timedelta(hours=i)
                    features = {
                        "temp": float(last_row.get("temp", 0.5)),
                        "humidity": float(last_row.get("hum", 0.5)),
                        "wind_speed": float(last_row.get("windspeed", 0.1)),
                        "hour": next_time.hour,
                        "day_of_week": next_time.dayofweek,
                        "month": next_time.month,
                    }
                    res = send_prediction(features)
                    pred = res.get("prediction", chart["cnt"].mean())
                    futures.append({"datetime": next_time, "cnt": pred})
            except Exception:
                # Fallback on failure
                for i in range(1, 4):
                    futures.append(
                        {
                            "datetime": last_date + pd.Timedelta(hours=i),
                            "cnt": chart["cnt"].mean(),
                        }
                    )

        chart = pd.concat([chart, pd.DataFrame(futures)])
        fig_main.add_trace(
            go.Scatter(
                x=chart["datetime"],
                y=chart["cnt"],
                mode="lines",
                fill="tozeroy",
                fillcolor="rgba(59,130,246,0.08)",
                line={"color": THEME["blue"], "width": 2},
                name="Demand",
            )
        )
        fig_main.update_layout(**PLOTLY_DEFAULTS)

    # --- Gauge ---
    fig_gauge = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(acc_val.replace("%", "")) if "%" in str(acc_val) else 94.2,
            gauge={
                "axis": {"range": [80, 100]},
                "bar": {"color": THEME["green"]},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0,
            },
            number={"suffix": "%", "font": {"size": 28, "color": THEME["text"]}},
        )
    )
    fig_gauge.update_layout(
        **{
            **PLOTLY_DEFAULTS,
            "height": 140,
            "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
        }
    )

    # --- Feature Importance ---
    if fi_data:
        sorted_fi = sorted(fi_data.items(), key=lambda x: x[1])
        features = [k for k, v in sorted_fi]
        importances = [v for k, v in sorted_fi]
    else:
        features = ["Temperature", "Hour", "Humidity", "Wind", "Season", "Day"]
        importances = [0.28, 0.22, 0.18, 0.12, 0.11, 0.09]

    fig_feat = go.Figure(
        go.Bar(
            x=importances,
            y=features,
            orientation="h",
            marker_color=[
                THEME["blue"],
                THEME["cyan"],
                THEME["green"],
                THEME["purple"],
                THEME["amber"],
                THEME["rose"],
            ][: len(features)],
        )
    )
    fig_feat.update_layout(
        **{
            **PLOTLY_DEFAULTS,
            "height": 150,
            "margin": {"l": 10, "r": 10, "t": 10, "b": 10},
            "yaxis": {
                "autorange": "reversed",
                "showgrid": False,
                "tickfont": {"size": 9, "color": THEME["text_secondary"]},
            },
            "xaxis": {"showgrid": False},
        }
    )

    # --- Predictions Table ---
    if not filtered.empty:
        recent = filtered.tail(5).copy()
        preds = []
        confs = []

        try:
            from api_client import send_prediction

            for _, row in recent.iterrows():
                dt = pd.to_datetime(row["datetime"])
                features_payload = {
                    "temp": float(row.get("temp", 0.5)),
                    "humidity": float(row.get("hum", 0.5)),
                    "wind_speed": float(row.get("windspeed", 0.1)),
                    "hour": dt.hour,
                    "day_of_week": dt.dayofweek,
                    "month": dt.month,
                }
                res = send_prediction(features_payload)
                preds.append(f"{res.get('prediction', 0):.1f}")
                confs.append(f"{res.get('confidence', 0):.0%}")
        except Exception:
            preds = ["N/A"] * len(recent)
            confs = ["N/A"] * len(recent)

        table_df = pd.DataFrame(
            {
                "Time": recent["datetime"].dt.strftime("%Y-%m-%d %H:%M"),
                "Actual": recent["cnt"],
                "Predicted": preds,
                "Confidence": confs,
            }
        )
        table = dbc.Table.from_dataframe(
            table_df, striped=True, bordered=False, hover=True, dark=True, size="sm"
        )
    else:
        table = html.Div("No prediction data available", className="text-muted p-3")

    # --- System Health ---
    from components.health_panel import create_health_panel

    sys_health = create_health_panel(services, drift_metrics, latest_report_name)

    # --- Drift Alert ---
    drift_alert = []
    if drift_metrics:
        dv = drift_metrics.get("evidently_dataset_drift", 0)
        ds = drift_metrics.get("evidently_drift_share", 0)
        if dv and dv > 0:
            drift_alert = [
                html.Div(
                    [
                        html.I(
                            className="bi bi-exclamation-triangle-fill",
                            style={
                                "color": "var(--danger)",
                                "fontSize": "1.125rem",
                                "flexShrink": 0,
                            },
                        ),
                        html.Div(
                            [
                                html.Strong("Data Drift Detected — "),
                                f"{ds:.0%} of features have drifted. Consider retraining.",
                            ],
                            className="drift-alert-text",
                        ),
                        html.Span(
                            f"{ds:.0%} Features", className="badge badge-danger ms-auto"
                        ),
                    ],
                    className="drift-alert",
                )
            ]

    # --- Model Metrics ---
    rmse = mae = mape = run_id = model_ver = env_tag = None
    if mlflow_run:
        rmse, mae, mape = (
            mlflow_run.get("rmse"),
            mlflow_run.get("mae"),
            mlflow_run.get("mape"),
        )
        run_id = (mlflow_run.get("run_id") or "")[:8] or None
        model_ver = mlflow_run.get("model_version")
        env_tag = mlflow_run.get("environment")

    def _metric_row(label, value, good_t=None, bad_t=None, fmt="{}", suffix=""):
        if value is None:
            return html.Div(
                [
                    html.Span(label, className="metric-label"),
                    html.Span("—", className="metric-value"),
                ],
                className="metric-row",
            )
        v = float(value)
        display = fmt.format(v) + suffix
        cls = "metric-value"
        if good_t is not None and bad_t is not None:
            cls += (
                " metric-good"
                if v <= good_t
                else (" metric-bad" if v >= bad_t else " metric-warn")
            )
        return html.Div(
            [
                html.Span(label, className="metric-label"),
                html.Span(display, className=cls),
            ],
            className="metric-row",
        )

    badges = []
    if run_id:
        badges.append(
            html.Span(
                [html.I(className="bi bi-hash me-1"), run_id],
                className="run-info-badge",
            )
        )
    if model_ver:
        badges.append(
            html.Span(
                [html.I(className="bi bi-tag me-1"), model_ver],
                className="run-info-badge",
            )
        )
    if env_tag:
        badges.append(
            html.Span(
                [html.I(className="bi bi-cloud me-1"), env_tag],
                className="run-info-badge",
            )
        )
    if not badges:
        badges.append(
            html.Span(
                "Demo Mode — connect MLflow for live metrics",
                className="run-info-badge text-warning",
            )
        )

    model_metrics = html.Div(
        [
            html.Div(
                badges, className="mb-3", style={"display": "flex", "flexWrap": "wrap"}
            ),
            _metric_row("RMSE", rmse, good_t=50, bad_t=120, fmt="{:.1f}"),
            _metric_row("MAE", mae, good_t=35, bad_t=90, fmt="{:.1f}"),
            _metric_row("MAPE", mape, good_t=5.0, bad_t=15.0, fmt="{:.2f}", suffix="%"),
        ]
    )

    return (
        kpi_total_val,
        kpi_total_trend,
        kpi_acc_val,
        kpi_acc_trend,
        kpi_resp_val,
        kpi_resp_trend,
        kpi_active_val,
        kpi_active_trend,
        fig_main,
        chart_title,
        fig_gauge,
        fig_feat,
        table,
        sys_health,
        drift_alert,
        model_metrics,
        latest_report_name or "",
    )
