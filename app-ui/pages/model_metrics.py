"""Model Metrics page — Performance tracking and drift monitoring."""

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from config_theme import THEME, PLOTLY_DEFAULTS

dash.register_page(__name__, path="/model-metrics", name="Model Health", order=3)


# Pre-styled empty figure — prevents white flash on initial load
def _empty_fig(height=250):
    fig = go.Figure()
    fig.update_layout(**{**PLOTLY_DEFAULTS, "height": height,
                         "xaxis": {"visible": False}, "yaxis": {"visible": False}})
    return fig


# ---------------------------------------------------------------------------
# Helpers (must be defined before layout)
# ---------------------------------------------------------------------------
def _metric_card(id_prefix, label, icon, color):
    return dbc.Col(
        html.Div(
            [
                html.I(className=f"bi {icon}", style={"color": color, "fontSize": "1.3rem"}),
                html.H3("—", id=f"{id_prefix}-value", className="metric-card-value mt-2"),
                html.Small(label, className="text-muted"),
            ],
            className="glass-card text-center p-3",
        ),
        xs=6, lg=3, className="mb-4",
    )


def _detail_row(label, value):
    return html.Div(
        [html.Span(label, className="metric-label"), html.Span(str(value), className="metric-value")],
        className="metric-row",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
layout = html.Div(
    [
        dcc.Interval(id="metrics-interval", interval=10000, n_intervals=0),

        html.Div(
            [
                html.H4("Model Health & Drift", className="page-title"),
                html.P(
                    "Track model degradation before it impacts operations. Evidently "
                    "monitors feature distributions against training baselines.",
                    className="page-description",
                ),
            ],
            className="page-header mb-4",
        ),

        # Top Row — Key Metrics
        dbc.Row(
            [
                _metric_card("metrics-rmse", "RMSE", "bi-rulers", THEME["blue"]),
                _metric_card("metrics-mae", "MAE", "bi-arrows-angle-contract", THEME["green"]),
                _metric_card("metrics-mape", "MAPE", "bi-percent", THEME["purple"]),
                _metric_card("metrics-drift-share", "Drift Share", "bi-graph-down", THEME["rose"]),
            ],
        ),

        # Mid Row — Drift Gauge + MLflow Runs
        dbc.Row(
            [
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(className="bi bi-speedometer me-2", style={"color": THEME["amber"]}),
                                    html.H6("Drift Score", className="mb-0 text-white"),
                                ],
                                className="d-flex align-items-center mb-3",
                            ),
                            dcc.Graph(id="drift-gauge", figure=_empty_fig(250), config={"displayModeBar": False}, style={"height": "250px"}),
                            html.P(
                                "Drift share represents the percentage of features that have "
                                "statistically drifted from the training distribution. A score above "
                                "10% typically warrants retraining.",
                                className="text-muted small mt-2",
                            ),
                        ],
                        className="glass-panel p-4 h-100",
                    ),
                    md=5, className="mb-4",
                ),
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(className="bi bi-list-check me-2", style={"color": THEME["blue"]}),
                                    html.H6("MLflow Run Details", className="mb-0 text-white"),
                                ],
                                className="d-flex align-items-center mb-3",
                            ),
                            html.Div(id="mlflow-run-details"),
                        ],
                        className="glass-panel p-4 h-100",
                    ),
                    md=7, className="mb-4",
                ),
            ],
        ),

        # Bottom — A/B Testing (if available)
        html.Div(id="ab-test-section"),
    ],
    className="page-model-metrics",
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
@callback(
    [
        Output("metrics-rmse-value", "children"),
        Output("metrics-mae-value", "children"),
        Output("metrics-mape-value", "children"),
        Output("metrics-drift-share-value", "children"),
        Output("drift-gauge", "figure"),
        Output("mlflow-run-details", "children"),
        Output("ab-test-section", "children"),
    ],
    Input("metrics-interval", "n_intervals"),
)
def update_model_metrics(n):
    best_run = None
    run_history = []
    drift_metrics = {}
    try:
        from api_client import get_best_mlflow_run, get_mlflow_run_history, get_drift_metrics
        best_run = get_best_mlflow_run()
        run_history = get_mlflow_run_history(n=5)
        drift_metrics = get_drift_metrics()
    except Exception:
        pass

    # ── Metric Card Values ────────────────────────────────────────────────────
    rmse = mae = mape = "—"
    if best_run:
        rmse = f"{best_run['rmse']:.2f}"   if best_run.get("rmse") is not None else "—"
        mae  = f"{best_run['mae']:.2f}"    if best_run.get("mae")  is not None else "—"
        mape = f"{best_run['mape']:.2f}%"  if best_run.get("mape") is not None else "—"

    drift_share = drift_metrics.get("evidently_drift_share", 0) or 0
    try:
        drift_share = float(drift_share)
    except (TypeError, ValueError):
        drift_share = 0.0
    drift_display = f"{drift_share:.1%}" if drift_share else "0%"

    # ── Drift Gauge ───────────────────────────────────────────────────────────
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=drift_share * 100,
        delta={"reference": 10, "increasing": {"color": THEME["rose"]}, "decreasing": {"color": THEME["green"]}},
        gauge=dict(
            axis=dict(range=[0, 100], ticksuffix="%"),
            bar=dict(color=THEME["amber"]),
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            steps=[
                {"range": [0, 10],  "color": "rgba(16,185,129,0.15)"},
                {"range": [10, 30], "color": "rgba(245,158,11,0.15)"},
                {"range": [30, 100],"color": "rgba(244,63,94,0.15)"},
            ],
            threshold=dict(line=dict(color=THEME["rose"], width=3), thickness=0.8, value=10),
        ),
        number=dict(suffix="%", font=dict(size=32, color=THEME["text"])),
    ))
    fig_gauge.update_layout(**{**PLOTLY_DEFAULTS, "height": 250, "margin": dict(l=20, r=20, t=20, b=20)})

    # ── MLflow Details Panel ──────────────────────────────────────────────────
    if best_run:
        model_type  = best_run.get("model_type", "CatBoost")
        run_name    = best_run.get("run_name") or best_run.get("run_id", "")[:8]
        model_ver   = best_run.get("model_version") or "—"
        pipeline_v  = best_run.get("pipeline_version") or "—"
        env_tag     = best_run.get("environment") or "—"
        start_time  = best_run.get("start_time", "—")
        params      = best_run.get("params") or {}

        # Readable hyperparameter names
        PARAM_LABELS = {
            "learning_rate":      "Learning Rate",
            "depth":              "Tree Depth",
            "iterations":         "Iterations",
            "l2_leaf_reg":        "L2 Leaf Reg",
            "border_count":       "Border Count",
            "random_strength":    "Random Strength",
            "bagging_temperature":"Bagging Temp",
            "min_data_in_leaf":   "Min Data/Leaf",
            "loss_function":      "Loss Function",
        }

        # ── Model Identity ────────────────────────────────
        model_badge_color = THEME["cyan"] if "catboost" in model_type.lower() else THEME["purple"]
        model_icon = "bi-cpu" if "catboost" in model_type.lower() else "bi-diagram-3"

        identity_section = html.Div([
            html.Div([
                html.I(className=f"bi {model_icon} me-2", style={"color": model_badge_color}),
                html.H6("Model Identity", className="mb-0 text-white"),
            ], className="d-flex align-items-center mb-3"),
            html.Div([
                html.Span(model_type, style={
                    "background": f"{model_badge_color}22",
                    "border": f"1px solid {model_badge_color}44",
                    "color": model_badge_color,
                    "padding": "3px 10px",
                    "borderRadius": "12px",
                    "fontSize": "0.8rem",
                    "fontWeight": 600,
                    "marginRight": "8px",
                }),
                html.Span("Optuna HPO", style={
                    "background": f"{THEME['amber']}22",
                    "border": f"1px solid {THEME['amber']}44",
                    "color": THEME["amber"],
                    "padding": "3px 10px",
                    "borderRadius": "12px",
                    "fontSize": "0.8rem",
                }),
            ], className="mb-3"),
            _detail_row("Best Run",        run_name),
            _detail_row("Trained",         start_time),
            _detail_row("Model Version",   model_ver),
            _detail_row("Pipeline",        pipeline_v),
            _detail_row("Environment",     env_tag),
        ], className="mb-4")

        # ── Hyperparameters ───────────────────────────────
        if params:
            param_rows = []
            for key, label in PARAM_LABELS.items():
                val = params.get(key)
                if val is not None:
                    try:
                        v = float(val)
                        formatted = f"{v:.4f}" if "." in str(val) and key not in ("depth", "iterations", "border_count", "min_data_in_leaf") else str(int(v))
                    except (ValueError, TypeError):
                        formatted = str(val)
                    param_rows.append(_detail_row(label, formatted))
            hp_section = html.Div([
                html.Div([
                    html.I(className="bi bi-sliders me-2", style={"color": THEME["purple"]}),
                    html.H6("Hyperparameters", className="mb-0 text-white"),
                ], className="d-flex align-items-center mb-3"),
                *param_rows,
            ], className="mb-4")
        else:
            hp_section = html.Div([
                html.Small("Hyperparameters not logged in this run.", className="text-muted"),
            ], className="mb-4")

        # ── Run History Table ─────────────────────────────
        if run_history:
            history_rows = []
            for i, r in enumerate(run_history):
                is_best = r.get("run_id") == best_run.get("run_id")
                rmse_v  = f"{r['rmse']:.2f}"  if r.get("rmse")  is not None else "—"
                mae_v   = f"{r['mae']:.2f}"   if r.get("mae")   is not None else "—"
                mape_v  = f"{r['mape']:.2f}%" if r.get("mape")  is not None else "—"
                run_short = (r.get("run_id") or "")[:8]
                row_style = {"borderLeft": f"2px solid {THEME['amber']}", "background": f"{THEME['amber']}08"} if is_best else {}
                history_rows.append(html.Tr([
                    html.Td([
                        run_short,
                        html.Span(" ★", style={"color": THEME["amber"]}) if is_best else "",
                    ], style={"fontSize": "0.75rem", "color": THEME["text_secondary"]}),
                    html.Td(r.get("start_time", "—"), style={"fontSize": "0.75rem", "color": THEME["text_secondary"]}),
                    html.Td(rmse_v, style={"color": THEME["cyan"], "fontWeight": 600, "fontSize": "0.8rem"}),
                    html.Td(mae_v,  style={"color": THEME["text_secondary"], "fontSize": "0.75rem"}),
                    html.Td(mape_v, style={"color": THEME["text_secondary"], "fontSize": "0.75rem"}),
                ], style=row_style))

            run_history_section = html.Div([
                html.Div([
                    html.I(className="bi bi-clock-history me-2", style={"color": THEME["cyan"]}),
                    html.H6("Run History (last 5)", className="mb-0 text-white"),
                ], className="d-flex align-items-center mb-3"),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Run", style={"color": THEME["text_secondary"], "fontSize": "0.7rem", "fontWeight": 600, "textTransform": "uppercase"}),
                        html.Th("Date",  style={"color": THEME["text_secondary"], "fontSize": "0.7rem", "fontWeight": 600, "textTransform": "uppercase"}),
                        html.Th("RMSE",  style={"color": THEME["text_secondary"], "fontSize": "0.7rem", "fontWeight": 600, "textTransform": "uppercase"}),
                        html.Th("MAE",   style={"color": THEME["text_secondary"], "fontSize": "0.7rem", "fontWeight": 600, "textTransform": "uppercase"}),
                        html.Th("MAPE",  style={"color": THEME["text_secondary"], "fontSize": "0.7rem", "fontWeight": 600, "textTransform": "uppercase"}),
                    ])),
                    html.Tbody(history_rows),
                ], style={"width": "100%", "borderCollapse": "collapse"}),
            ])
        else:
            run_history_section = html.Div(
                html.Small("No completed runs found in MLflow.", className="text-muted")
            )

        details = html.Div([identity_section, hp_section, run_history_section])

    else:
        details = html.Div([
            html.I(className="bi bi-info-circle me-2"),
            "MLflow unavailable — connect the tracking server to see live run details.",
        ], className="text-muted p-3")

    # ── A/B Testing Section ───────────────────────────────────────────────────
    ab_section = []
    try:
        import requests
        from api_client import MODEL_SERVER_URL
        resp = requests.get(f"{MODEL_SERVER_URL}/ab/stats", timeout=3)
        if resp.status_code == 200:
            ab = resp.json()
            ab_section = [html.Div([
                html.Div([html.I(className="bi bi-shuffle me-2", style={"color": THEME["cyan"]}),
                          html.H6("A/B Test Results", className="mb-0 text-white")],
                         className="d-flex align-items-center mb-3"),
                html.Pre(str(ab), className="text-muted small"),
            ], className="glass-panel p-4")]
    except Exception:
        pass

    return rmse, mae, mape, drift_display, fig_gauge, details, ab_section
