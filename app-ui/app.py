import os
import sys
from pathlib import Path
import dash
from dash import html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.express as px
import pandas as pd

# Setup paths
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))
sys.path.append(os.path.join(project_root, 'app-ml', 'src'))
os.chdir(project_root)

from common.utils import read_config

# Load Configuration
config_path = project_root / 'config' / 'config.yaml'
config = read_config(config_path)

# Load Data
try:
    data_path = project_root / config['data_manager']['raw_data_path']
    df = pd.read_parquet(data_path)
    
    # Preprocessing
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    season_map = {1: 'Spring', 2: 'Summer', 3: 'Fall', 4: 'Winter'}
    df['season_label'] = df['season'].map(season_map)
    
    # Global KPIs (computed once)
    total_demand_all = df['cnt'].sum()
    avg_temp_all = df['temp'].mean()
    total_registered_all = df['registered'].sum()

except Exception as e:
    print(f"Error loading data: {e}")
    df = pd.DataFrame()

# Initialize App with LUMEN theme (Professional/Light)
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUMEN, dbc.icons.BOOTSTRAP])
server = app.server
app.title = "Demand Forecasting"

# Helper function for chart styling
def style_figure(fig):
    fig.update_layout(
        template='plotly_white',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#455A64'), # Slate text
        xaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
        yaxis=dict(showgrid=True, gridcolor='#e0e0e0'),
        margin=dict(l=40, r=20, t=40, b=40),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Segoe UI")
    )
    return fig

app.layout = html.Div([
    # Navbar
    dbc.NavbarSimple(
        brand="Demand Forecasting System",
        brand_href="#",
        color="transparent",
        dark=False,
        fluid=True,
        className="custom-navbar mb-4"
    ),

    dbc.Container([
        # Hero Section
        html.Div([
            html.Div([
                html.H1("URBAN FLOW CYCLING", className="hero-title"),
                html.P("Smart Demand Forecasting & Mobility Analytics", className="hero-subtitle")
            ], className="hero-overlay")
        ], className="hero-container"),

        # Filter Row
        dbc.Row([
            dbc.Col([
                html.Label("Select Date Range", className="fw-bold text-slate"),
                dcc.DatePickerRange(
                    id='date-picker-range',
                    min_date_allowed=df['date'].min(),
                    max_date_allowed=df['date'].max(),
                    start_date=df['date'].min(),
                    end_date=df['date'].max(),
                    className="mb-2 d-block",
                ),
            ], width=12, md=6),
            dbc.Col([
                html.Label("Select Seasons", className="fw-bold text-slate"),
                dcc.Dropdown(
                    id='season-dropdown',
                    options=[{'label': s, 'value': s} for s in season_map.values()],
                    value=list(season_map.values()),
                    multi=True,
                    clearable=False
                )
            ], width=12, md=6)
        ], className="mb-4"),

        # KPI Row
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Total Rentals"),
                dbc.CardBody(html.H3(id='kpi-demand', className="text-forest"))
            ], className="pro-card mb-4"), width=12, md=4),
            
            dbc.Col(dbc.Card([
                dbc.CardHeader("Avg. Temp (Norm)"),
                dbc.CardBody(html.H3(id='kpi-temp', className="text-science-blue"))
            ], className="pro-card mb-4"), width=12, md=4),
            
            dbc.Col(dbc.Card([
                dbc.CardHeader("Registered Users"),
                dbc.CardBody(html.H3(id='kpi-users', className="text-slate"))
            ], className="pro-card mb-4"), width=12, md=4),
        ]),

        # Charts
        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Daily Demand Trends"),
                dbc.CardBody(dcc.Graph(id='fig-demand', config={'displayModeBar': 'hover'}))
            ], className="pro-card mb-4"), width=12),
        ]),

        dbc.Row([
            dbc.Col(dbc.Card([
                dbc.CardHeader("Seasonality Distribution"),
                dbc.CardBody(dcc.Graph(id='fig-seasonality', config={'displayModeBar': 'hover'}))
            ], className="pro-card mb-4"), width=12, lg=6),

            dbc.Col(dbc.Card([
                dbc.CardHeader("Temperature Impact"),
                dbc.CardBody(dcc.Graph(id='fig-corr', config={'displayModeBar': 'hover'}))
            ], className="pro-card mb-4"), width=12, lg=6),
        ])

    ], fluid=True)
])

@callback(
    [Output('kpi-demand', 'children'),
     Output('kpi-temp', 'children'),
     Output('kpi-users', 'children'),
     Output('fig-demand', 'figure'),
     Output('fig-seasonality', 'figure'),
     Output('fig-corr', 'figure')],
    [Input('date-picker-range', 'start_date'),
     Input('date-picker-range', 'end_date'),
     Input('season-dropdown', 'value')]
)
def update_dashboard(start_date, end_date, selected_seasons):
    # Filter Data
    mask = (df['date'] >= pd.to_datetime(start_date).date()) & \
           (df['date'] <= pd.to_datetime(end_date).date()) & \
           (df['season_label'].isin(selected_seasons))
    filtered_df = df.loc[mask]
    
    # Recalculate KPIs
    k_demand = filtered_df['cnt'].sum()
    k_temp = filtered_df['temp'].mean()
    k_users = filtered_df['registered'].sum()
    
    # 1. Daily Trend
    daily_data = filtered_df.groupby('date')['cnt'].sum().reset_index()
    fig1 = px.line(daily_data, x='date', y='cnt', title=None)
    fig1.update_traces(line_color='#2E7D32', line_width=3) # Forest Green
    fig1 = style_figure(fig1)

    # 2. Seasonality
    # Eco-friendly palette: Green, Gold, Orange, Blue
    season_colors = {'Spring': '#66BB6A', 'Summer': '#FDD835', 'Fall': '#FF7043', 'Winter': '#42A5F5'}
    fig2 = px.box(filtered_df, x='season_label', y='cnt', color='season_label',
                  category_orders={'season_label': ['Spring', 'Summer', 'Fall', 'Winter']},
                  color_discrete_map=season_colors)
    fig2.update_layout(showlegend=False)
    fig2 = style_figure(fig2)
    
    # 3. Correlation
    # Sample down if too large
    plot_df = filtered_df if len(filtered_df) < 5000 else filtered_df.sample(5000)
    fig3 = px.scatter(plot_df, x='temp', y='cnt', color='season_label', opacity=0.6,
                      color_discrete_map=season_colors)
    fig3 = style_figure(fig3)

    return f"{k_demand:,.0f}", f"{k_temp:.2f}", f"{k_users:,.0f}", fig1, fig2, fig3

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=8050)