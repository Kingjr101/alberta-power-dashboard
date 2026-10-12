"""Plotly figures with shared units, colors and honest chart scales."""
import calendar

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.analysis import daily_market, demand_bands, monthly_spikes, patterns, price_duration, relationship

TEAL = "#087f73"
INK = "#203d45"
MUTED = "#60777c"
AMBER = "#b65b22"
PALE = "#d7ebe6"
GRID = "#e6eeeb"


def style(fig, height=380):
    fig.update_layout(template="plotly_white", height=height,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Arial, sans-serif", size=12, color=INK),
                      margin=dict(l=12, r=16, t=30, b=20),
                      legend=dict(orientation="h", y=1.12, x=0, font=dict(size=11)),
                      hoverlabel=dict(bgcolor="white", font_color=INK),
                      colorway=[TEAL, AMBER, MUTED], dragmode=False)
    fig.update_xaxes(showgrid=False, zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True)
    return fig


def market_timeline(data, show_range=True):
    daily = daily_market(data)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_heights=[0.70, 0.30])
    if show_range:
        fig.add_trace(go.Scatter(x=daily.date, y=daily.low, line=dict(width=0), showlegend=False, hoverinfo="skip"), row=1, col=1)
        fig.add_trace(go.Scatter(x=daily.date, y=daily.high, fill="tonexty", fillcolor="rgba(8,127,115,0.10)",
                                 line=dict(width=0), name="Hourly range", hovertemplate="Daily high: $%{y:.2f}<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=daily.date, y=daily["mean"], name="Daily average", line=dict(color=TEAL, width=1.6), hovertemplate="$%{y:.2f}/MWh<extra>Daily average</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=daily.date, y=daily["rolling"], name="7-day mean", line=dict(color=INK, width=2.3), hovertemplate="$%{y:.2f}/MWh<extra>7-day mean</extra>"), row=1, col=1)
    fig.add_trace(go.Scatter(x=daily.date, y=daily.load, name="Daily AIL", line=dict(color=MUTED, width=1.5), showlegend=False,
                             hovertemplate="%{y:,.0f} MW<extra>Daily average load</extra>"), row=2, col=1)
    fig.update_yaxes(title_text="CAD/MWh", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="Load · MW", tickformat=",.0f", row=2, col=1)
    style(fig, 460)
    fig.update_layout(hovermode="x unified", legend=dict(y=1.08))
    return fig


def distribution(data):
    p = data.pool_price_cad_mwh
    # Fixed economic bands, including the exact $500 boundary in the non-spike bin.
    bins = [-np.inf, 0, 25, 50, 100, 250, 500, np.inf]
    labels = ["≤ $0", "$0–25", "$25–50", "$50–100", "$100–250", "$250–500", "> $500"]
    counts = pd.cut(p, bins=bins, labels=labels).value_counts(sort=False)
    share = counts / len(data) * 100
    fig = go.Figure(go.Bar(x=share, y=labels, orientation="h", marker_color=[AMBER if i == 6 else TEAL for i in range(7)],
                           text=[f"{v:.1f}%" for v in share], textposition="outside", cliponaxis=False,
                           customdata=counts, hovertemplate="%{y}/MWh<br>%{customdata:,} hours · %{x:.2f}%<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Share of hours (%)", range=[0, max(share.max() * 1.25, 5)])
    return style(fig, 350)


def price_load(data):
    correlation, line = relationship(data)
    fig = go.Figure()
    for mask, name, color, opacity in [(data.pool_price_cad_mwh <= 500, "≤ $500/MWh", TEAL, 0.20),
                                       (data.pool_price_cad_mwh > 500, "> $500/MWh", AMBER, 0.65)]:
        d = data.loc[mask]
        fig.add_trace(go.Scattergl(x=d.ail_mw, y=d.pool_price_cad_mwh, mode="markers", name=name,
                                   marker=dict(size=4, color=color, opacity=opacity), customdata=d.timestamp_alberta,
                                   hovertemplate="%{customdata}<br>%{x:,.0f} MW · $%{y:.2f}/MWh<extra></extra>"))
    if not line.empty:
        fig.add_trace(go.Scatter(x=line.ail_mw, y=line.pool_price_cad_mwh, name="Linear trend", mode="lines", line=dict(color=INK, width=2.5)))
    fig.update_xaxes(title="Actual Alberta Internal Load (MW)", tickformat=",.0f")
    fig.update_yaxes(title="Pool price (CAD/MWh)", rangemode="tozero")
    return style(fig, 480)


def demand_comparison(data, risk=False):
    bands = demand_bands(data)
    ranges = [f"{row.load_min:,.0f}–{row.load_max:,.0f} MW" for row in bands.itertuples()]
    fig = go.Figure()
    if risk:
        fig.add_trace(go.Bar(x=bands.band, y=bands.spike_percent, marker_color=AMBER, customdata=ranges,
                             text=[f"{v:.2f}%" for v in bands.spike_percent], textposition="outside", cliponaxis=False,
                             hovertemplate="%{customdata}<br>%{y:.2f}% of hours > $500<extra></extra>"))
        fig.update_yaxes(title="Hours above $500 (%)", range=[0, max(1, bands.spike_percent.max() * 1.25)])
    else:
        for column, name, color in [("mean", "Average", TEAL), ("median", "Median", MUTED)]:
            fig.add_trace(go.Scatter(x=bands.band, y=bands[column], mode="lines+markers", name=name,
                                     line=dict(color=color, width=2), marker=dict(size=8), customdata=ranges,
                                     hovertemplate="%{customdata}<br>$%{y:.2f}/MWh<extra>" + name + "</extra>"))
        fig.update_yaxes(title="Price (CAD/MWh)", rangemode="tozero")
    fig.update_xaxes(title="Demand bands · lowest to highest")
    return style(fig, 340)


def hourly_profile(data):
    p = data.groupby("hour").pool_price_cad_mwh.agg(["mean", "median"]).reindex(range(24))
    fig = go.Figure()
    for col, title, color in [("mean", "Average", TEAL), ("median", "Median", MUTED)]:
        fig.add_trace(go.Scatter(x=p.index, y=p[col], mode="lines+markers", name=title, line=dict(color=color, width=2.5),
                                 marker=dict(size=5), hovertemplate="%{x:02d}:00<br>$%{y:.2f}/MWh<extra>" + title + "</extra>"))
    hour = p["mean"].idxmax()
    fig.add_trace(go.Scatter(x=[hour], y=[p.loc[hour, "mean"]], mode="markers", marker=dict(size=11, color=AMBER),
                             name="Highest average", hovertemplate="%{x:02d}:00 · $%{y:.2f}/MWh<extra></extra>"))
    fig.update_xaxes(title="Hour beginning · Alberta time", tickvals=[0, 4, 8, 12, 16, 20, 23])
    fig.update_yaxes(title="Price (CAD/MWh)", rangemode="tozero")
    return style(fig, 340)


def monthly_profile(data):
    year = data.timestamp_utc.dt.tz_convert("America/Edmonton").dt.year
    frame = data.assign(year=year).groupby(["year", "month"]).pool_price_cad_mwh.mean()
    fig = go.Figure()
    for i, y in enumerate(sorted(year.unique())):
        values = frame.loc[y].reindex(range(1, 13))
        fig.add_trace(go.Bar(x=[calendar.month_abbr[m] for m in values.index], y=values, name=str(y),
                             marker_color=[TEAL, MUTED, AMBER][i % 3], hovertemplate="%{x}<br>$%{y:.2f}/MWh<extra>" + str(y) + "</extra>"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Average price (CAD/MWh)", rangemode="tozero")
    return style(fig, 340)


def season_heatmap(data):
    _, _, heat = patterns(data)
    fig = go.Figure(go.Heatmap(z=heat.values, x=[calendar.month_abbr[m] for m in heat.columns], y=[f"{h:02d}:00" for h in heat.index],
                              colorscale=[[0, "#f0f6f3"], [0.3, "#a5d5c7"], [0.65, TEAL], [1, "#143e38"]],
                              xgap=3, ygap=3, colorbar=dict(title="CAD/MWh", thickness=12), hoverongaps=False,
                              hovertemplate="%{x} · %{y}<br>Average $%{z:.2f}/MWh<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title="Hour beginning · Alberta time", dtick=2)
    fig.update_xaxes(side="top")
    return style(fig, 560)


def spike_frequency(data, percent=True):
    frame = monthly_spikes(data)
    y = frame.percent if percent else frame.spikes
    fig = go.Figure(go.Bar(x=frame.period, y=y, marker_color=AMBER,
                           customdata=frame[["spikes", "hours", "percent"]],
                           hovertemplate="%{x}<br>%{customdata[0]:,} spike hours / %{customdata[1]:,} observed<br>%{customdata[2]:.2f}%<extra></extra>"))
    fig.update_yaxes(title="Share of observed hours (%)" if percent else "Hours above $500/MWh", rangemode="tozero")
    return style(fig, 340)


def duration_curve(data):
    frame = price_duration(data)
    fig = go.Figure(go.Scatter(x=frame.share, y=frame.pool_price_cad_mwh, mode="lines", line=dict(color=TEAL, width=2.5),
                               hovertemplate="Top %{x:.2f}% of hours<br>$%{y:.2f}/MWh<extra></extra>"))
    fig.add_hline(y=500, line_dash="dot", line_color=AMBER, annotation_text="$500 spike threshold", annotation_position="top right")
    fig.update_xaxes(title="Cumulative share of hours, highest price first (%)", range=[0, 100])
    fig.update_yaxes(title="Price (CAD/MWh)", rangemode="tozero")
    return style(fig, 340)
