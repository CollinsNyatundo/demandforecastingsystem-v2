"""System health panel component for the UrbanFlow dashboard."""

from dash import html


def create_health_panel(services, drift_metrics=None, latest_report_name=None):
    """Build the system health items list with colored left-border indicators."""
    health_items = []

    for svc in services:
        is_healthy = svc.get("healthy", False)
        is_demo = svc.get("status", "").lower() in ("demo", "simulated")

        if is_healthy:
            status_icon = "bi-check-circle-fill text-success"
            health_class = "health-item health-ok"
        elif is_demo:
            status_icon = "bi-question-circle-fill text-warning"
            health_class = "health-item health-demo"
        else:
            status_icon = "bi-x-circle-fill text-danger"
            health_class = "health-item health-down"

        # Inject Airflow Trigger Button
        actions = []
        if svc["name"] == "Airflow Pipeline":
            actions.append(
                html.Button(
                    "Retrain",
                    id="btn-trigger-retrain",
                    n_clicks=0,
                    className="btn btn-sm btn-outline-info me-3 py-0 px-2 fs-7",
                )
            )

        actions.append(html.I(className=f"{status_icon} fs-5"))

        health_items.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.I(className=f"{svc['icon']} me-3 {svc['color']} fs-4"),
                            html.Div(
                                [
                                    html.Div(
                                        svc["name"], className="fw-bold text-white"
                                    ),
                                    html.Div(
                                        f"{svc['status']} — {svc['detail']}",
                                        className="text-muted small",
                                    ),
                                ]
                            ),
                        ],
                        className="d-flex align-items-center",
                    ),
                    html.Div(actions, className="d-flex align-items-center"),
                ],
                className=health_class + " justify-content-between d-flex",
            )
        )

    # Add drift status badge
    if drift_metrics:
        drift_val = drift_metrics.get("evidently_dataset_drift", 0)
        drift_share = float(drift_metrics.get("evidently_drift_share", 0))
        drift_color = "text-danger" if drift_val > 0 else "text-success"
        drift_label = (
            f"Data Drift: {'DETECTED' if drift_val > 0 else 'None'} "
            f"({drift_share:.1%} features)"
        )

        actions = []
        if latest_report_name:
            actions.append(
                html.Button(
                    "View Report",
                    id="btn-view-drift-report",
                    n_clicks=0,
                    className=f"btn btn-sm btn-outline-{'danger' if drift_val > 0 else 'success'} me-3 py-0 px-2 fs-7",
                )
            )
        actions.append(
            html.I(
                className=f"bi bi-{'exclamation' if drift_val > 0 else 'check'}-circle-fill {drift_color} fs-5"
            )
        )

        health_items.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.I(
                                className=f"bi bi-graph-down me-3 {drift_color} fs-4"
                            ),
                            html.Div(
                                [
                                    html.Div(
                                        "Data Drift Monitor",
                                        className="fw-bold text-white",
                                    ),
                                    html.Div(
                                        drift_label, className=f"{drift_color} small"
                                    ),
                                ]
                            ),
                        ],
                        className="d-flex align-items-center",
                    ),
                    html.Div(actions, className="d-flex align-items-center"),
                ],
                className="health-item justify-content-between d-flex",
            )
        )

    return (
        html.Div(health_items)
        if health_items
        else html.Div("No services available", className="text-muted")
    )
