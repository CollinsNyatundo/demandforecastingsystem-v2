"""Predictions page — Interactive prediction interface for data scientists."""

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

from config_theme import THEME

dash.register_page(__name__, path="/predictions", name="Predictions", order=2)


# ---------------------------------------------------------------------------
# Helpers (must be defined before layout)
# ---------------------------------------------------------------------------
def _slider(id_, label, mn, mx, val, step, hint):
    return html.Div(
        [
            html.Div(
                [
                    html.Label(label, className="slider-label"),
                    html.Small(hint, className="text-muted ms-auto"),
                ],
                className="d-flex justify-content-between align-items-end mb-1",
            ),
            dcc.Slider(
                id=id_, min=mn, max=mx, value=val, step=step,
                marks=None, tooltip={"placement": "bottom", "always_visible": True},
                persistence=True, persistence_type="session",
                className="custom-slider",
            ),
        ],
        className="mb-3",
    )


def _empty_result():
    return html.Div(
        [
            html.Div("—", className="pred-result-value"),
            html.Small("Adjust features and click Run Prediction", className="text-muted"),
        ],
        className="text-center py-4",
    )


def _result_chip(label, value, color):
    return html.Div(
        [
            html.Small(label, className="text-muted d-block"),
            html.Span(value, style={"color": color, "fontWeight": 600}),
        ],
        className="text-center",
    )


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
layout = html.Div(
    [
        html.Div(
            [
                html.H4("Live Predictions", className="page-title"),
                html.P(
                    "Test the demand model with custom feature inputs. Each prediction "
                    "is logged and scored against real outcomes for continuous learning.",
                    className="page-description",
                ),
            ],
            className="page-header mb-4",
        ),

        dbc.Row(
            [
                # Left — Input form
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.I(className="bi bi-sliders me-2", style={"color": THEME["cyan"]}),
                                    html.H6("Feature Inputs", className="mb-0 text-white"),
                                ],
                                className="d-flex align-items-center mb-4",
                            ),
                            _slider("pred-temp", "Temperature", 0, 1, 0.5, 0.01, "Normalized (0–1)"),
                            _slider("pred-humidity", "Humidity", 0, 1, 0.65, 0.01, "Normalized (0–1)"),
                            _slider("pred-wind", "Wind Speed", 0, 1, 0.15, 0.01, "Normalized (0–1)"),
                            _slider("pred-hour", "Hour of Day", 0, 23, 14, 1, "0 = midnight, 23 = 11pm"),
                            _slider("pred-day", "Day of Week", 0, 6, 3, 1, "0 = Monday, 6 = Sunday"),
                            _slider("pred-month", "Month", 1, 12, 6, 1, "1 = January, 12 = December"),

                            html.Div(
                                dbc.Button(
                                    [html.I(className="bi bi-lightning-charge me-2"), "Run Prediction"],
                                    id="pred-submit",
                                    color="primary",
                                    className="w-100 mt-3",
                                    size="lg",
                                ),
                                className="mt-2",
                            ),
                        ],
                        className="glass-panel p-4",
                    ),
                    md=5, className="mb-4",
                ),

                # Right — Result + Scenarios + History
                dbc.Col(
                    [
                        # Results
                        dbc.Row([
                            dbc.Col([
                                html.Div(
                                    [
                                        html.I(className="bi bi-bullseye me-2", style={"color": THEME["green"]}),
                                        html.H6("Baseline Prediction", className="mb-0 text-white"),
                                    ],
                                    className="d-flex align-items-center mb-3",
                                ),
                                dcc.Loading(
                                    type="dot", color=THEME["blue"],
                                    children=html.Div(id="pred-result", children=_empty_result())
                                ),
                            ], md=6, className="border-end border-secondary border-opacity-25 pe-3"),
                            dbc.Col([
                                html.Div(
                                    [
                                        html.I(className="bi bi-magic me-2", style={"color": THEME["purple"]}),
                                        html.H6("What-If Scenario", className="mb-0 text-white"),
                                    ],
                                    className="d-flex align-items-center mb-3",
                                ),
                                dcc.Loading(
                                    type="dot", color=THEME["purple"],
                                    children=html.Div(id="scenario-result", children=_empty_result())
                                ),
                                html.P("Quick Scenarios:", className="text-muted small mt-3 mb-1"),
                                html.Div([
                                    dbc.Button("+20% Temp", id="btn-scen-temp", size="sm", className="me-2", outline=True, color="warning"),
                                    dbc.Button("Weekend", id="btn-scen-weekend", size="sm", className="me-2", outline=True, color="info"),
                                    dbc.Button("High Wind", id="btn-scen-wind", size="sm", outline=True, color="secondary"),
                                ])
                            ], md=6, className="ps-3"),
                        ], className="glass-panel p-4 mb-4 gx-0"),
                        
                        # History
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.I(className="bi bi-clock-history me-2", style={"color": THEME["purple"]}),
                                        html.H6("Prediction History", className="mb-0 text-white"),
                                    ],
                                    className="d-flex align-items-center mb-3",
                                ),
                                html.Div(id="pred-history", children=html.Div("Run a prediction to see history here.", className="text-muted small")),
                            ],
                            className="glass-panel p-4",
                        ),
                    ],
                    md=7,
                ),
            ],
        ),
        # Store for history
        dcc.Store(id="pred-history-store", data=[]),
    ],
    className="page-predictions",
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
@callback(
    [
        Output("pred-result", "children"), 
        Output("scenario-result", "children"), 
        Output("pred-history", "children"), 
        Output("pred-history-store", "data")
    ],
    [
        Input("pred-submit", "n_clicks"),
        Input("btn-scen-temp", "n_clicks"),
        Input("btn-scen-weekend", "n_clicks"),
        Input("btn-scen-wind", "n_clicks"),
    ],
    [
        State("pred-temp", "value"),
        State("pred-humidity", "value"),
        State("pred-wind", "value"),
        State("pred-hour", "value"),
        State("pred-day", "value"),
        State("pred-month", "value"),
        State("pred-history-store", "data"),
    ],
    prevent_initial_call=True,
)
def run_prediction(n_submit, n_temp, n_weekend, n_wind, temp, humidity, wind, hour, day, month, history):
    from datetime import datetime
    from dash import ctx

    trigger = ctx.triggered_id or "pred-submit"

    features = {
        "temp": temp, "humidity": humidity, "wind_speed": wind,
        "hour": int(hour), "day_of_week": int(day), "month": int(month),
    }

    # Setup Scenario
    scen_features = None
    scen_name = ""
    scen_desc = ""
    if trigger == "btn-scen-temp":
        scen_features = features.copy()
        scen_features["temp"] = min(1.0, features["temp"] * 1.2)
        scen_name = "Hotter Day (+20% Temp)"
        scen_desc = f"Temp: {scen_features['temp']:.2f}"
    elif trigger == "btn-scen-weekend":
        scen_features = features.copy()
        scen_features["day_of_week"] = 6
        scen_name = "Weekend (Sunday)"
        scen_desc = f"Day: Sunday"
    elif trigger == "btn-scen-wind":
        scen_features = features.copy()
        scen_features["wind_speed"] = min(1.0, features["wind_speed"] * 2.5) if features["wind_speed"] > 0 else 0.5
        scen_name = "High Wind (Stormy)"
        scen_desc = f"Wind: {scen_features['wind_speed']:.2f}"

    def build_card(pred_val, conf, m_version, latency, title_prefix="Demand", subtitle="rides/hour", extra_elements=None):
        if pred_val is None:
            return html.Div("Error: Live Model Unavailable", className="text-danger p-3")
        c_color = THEME["green"] if conf > 0.9 else (THEME["amber"] if conf > 0.8 else THEME["rose"])
        els = [
            html.Div(
                [
                    html.Span(title_prefix, className="text-muted small"),
                    html.H2(f"{pred_val:,.1f}", style={"color": THEME["cyan"], "fontFamily": "JetBrains Mono, monospace"}),
                    html.Span(subtitle, className="text-muted small d-block"),
                ],
                className="text-center mb-3",
            ),
            html.Div(
                [
                    _result_chip("Conf", f"{conf:.0%}", c_color),
                    _result_chip("Latency", f"{latency}ms", THEME["purple"]),
                ],
                className="d-flex justify-content-center gap-2",
            ),
        ]
        if extra_elements:
            els.extend(extra_elements)
        return html.Div(els)

    prediction = None
    confidence = 0.0
    model_version = ""
    baseline_latency = 0
    
    scen_prediction = None
    scen_confidence = 0.0
    scen_lat = 0

    try:
        from api_client import send_prediction
        # Run Baseline
        res = send_prediction(features)
        if "prediction" in res:
            prediction = res["prediction"]
            confidence = res.get("confidence", 0.0)
            model_version = res.get("model_version", "unknown")
            baseline_latency = res.get("latency_ms", 0)
            
        # Run Scenario if triggered
        if scen_features:
            scen_res = send_prediction(scen_features)
            if "prediction" in scen_res:
                scen_prediction = scen_res["prediction"]
                scen_confidence = scen_res.get("confidence", 0.0)
                scen_lat = scen_res.get("latency_ms", 0)
    except Exception as e:
        import logging
        logging.error("Live prediction failed: %s", e)

    if prediction is None:
        return html.Div("Error: Live Model Server Unreachable", className="text-danger p-3"), dash.no_update, dash.no_update, dash.no_update

    res_card = build_card(prediction, confidence, model_version, baseline_latency)
    
    scen_card = _empty_result()
    if scen_features and scen_prediction is not None:
        diff = scen_prediction - prediction
        diff_color = THEME["green"] if diff > 0 else THEME["rose"]
        diff_str = f"{'+' if diff > 0 else ''}{diff:.1f}"
        scen_card = build_card(
            scen_prediction, scen_confidence, model_version, scen_lat,
            title_prefix=scen_name, 
            extra_elements=[
                html.Div([
                    html.Span(scen_desc, className="badge bg-secondary me-2"),
                    html.Span(f"Δ {diff_str}", style={"color": diff_color, "fontWeight": "bold", "fontSize": "0.9em"})
                ], className="text-center mt-3")
            ]
        )

    # Update history with baseline
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "prediction": round(prediction, 1),
        "confidence": f"{confidence:.0%}",
        "temp": temp, "hour": int(hour),
    }
    history = (history or [])[-19:]
    history.append(entry)

    history_rows = []
    for h in reversed(history[-10:]):
        history_rows.append(
            html.Div(
                [
                    html.Span(h["time"], className="text-muted small", style={"width": "70px"}),
                    html.Span(f"{h['prediction']}", className="text-white fw-bold", style={"width": "80px"}),
                    html.Span(h["confidence"], className="badge badge-success", style={"width": "50px"}),
                    html.Span(f"T={h['temp']:.1f} H={h['hour']}", className="text-muted small"),
                ],
                className="pred-history-row",
            )
        )

    return res_card, scen_card, html.Div(history_rows), history
