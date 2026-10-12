"""Run with: streamlit run app.py."""
import calendar
import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analysis import filter_dates, insights, patterns, prepare, relationship, spikes, summary

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Alberta Power | Price & Demand", page_icon="⚡", layout="wide")


@st.cache_data
def load_data():
    return prepare(pd.read_csv(ROOT / "data/hourly.csv"))


def chart(figure):
    figure.update_layout(margin=dict(l=10, r=10, t=35, b=15), font=dict(size=13),
                         colorway=["#087f8c", "#ef8354"], hovermode="closest")
    st.plotly_chart(figure, width="stretch", config={"displayModeBar": False})


data = load_data()
metadata = json.loads((ROOT / "data/metadata.json").read_text())
with st.sidebar:
    st.title("⚡ Alberta Power")
    st.caption("Wholesale electricity · AESO")
    dates = st.date_input("Date range", value=(data.date.min(), data.date.max()),
                          min_value=data.date.min(), max_value=data.date.max())
    page = st.radio("Explore", ["Overview", "Price vs. load", "Patterns", "Price spikes"])
    st.divider()
    st.caption(f"Snapshot: {metadata['start_date']} to {metadata['end_date']}\n\n{len(data):,} hourly observations · Alberta local time")
    st.caption("Prices: CAD/MWh · Actual AIL: MW\n\nWholesale prices are not retail electricity bills.")
    st.link_button("Source: AESO", "https://www.aeso.ca/market/market-and-system-reporting/aeso-application-programming-interface-api/")

st.title("Alberta electricity: price & demand")
st.caption("An hourly look at Alberta’s wholesale market, built with real AESO pool prices and Alberta Internal Load.")
if len(dates) != 2:
    st.info("Select an end date to complete the date range.")
    st.stop()
selected = filter_dates(data, *dates)
if selected.empty:
    st.info("No observations in this date range.")
    st.stop()
stats = summary(selected)
st.subheader(page)
st.caption(f"{dates[0]:%b %d, %Y} – {dates[1]:%b %d, %Y} · {len(selected):,} hours")

if page == "Overview":
    columns = st.columns(3)
    for column, label, key in zip(columns, ["Average price", "Maximum price", "Minimum price"], ["mean", "max", "min"]):
        column.metric(label, f"${stats[key]:,.2f}", help="CAD per MWh; unweighted hourly price")
    daily = selected.groupby("date", as_index=False).agg(price=("pool_price_cad_mwh", "mean"), load=("ail_mw", "mean"))
    chart(px.line(daily, x="date", y="price", labels={"date": "Date", "price": "Daily average price (CAD/MWh)"}))
    st.subheader("What I found")
    for finding in insights(selected):
        st.markdown("- " + finding.replace("$", r"\$"))
    st.caption("Findings update with the date filter. Demand alone does not explain prices; generation availability, fuel costs and imports also matter.")
elif page == "Price vs. load":
    correlation, line = relationship(selected)
    st.metric("Pearson correlation", f"{correlation:.3f}" if pd.notna(correlation) else "Not defined")
    figure = px.scatter(selected, x="ail_mw", y="pool_price_cad_mwh", opacity=0.25,
                         hover_data=["timestamp_alberta"], render_mode="webgl",
                         labels={"ail_mw": "Actual Alberta Internal Load (MW)", "pool_price_cad_mwh": "Pool price (CAD/MWh)"})
    figure.update_traces(marker=dict(size=4, color="#087f8c"))
    if not line.empty:
        figure.add_trace(go.Scatter(x=line.ail_mw, y=line.pool_price_cad_mwh, mode="lines", name="Linear trend (OLS)", line=dict(color="#ef8354", width=3)))
    chart(figure)
    st.caption("Each dot is one hour; all selected hours are included. The line is an ordinary least-squares fit. Correlation measures linear association, not causation or forecast accuracy.")
elif page == "Patterns":
    hourly, monthly, heatmap = patterns(selected)
    chart(px.bar(x=hourly.index, y=hourly.values, labels={"x": "Hour beginning (Alberta time)", "y": "Average price (CAD/MWh)"}))
    chart(px.bar(x=[calendar.month_abbr[m] for m in monthly.index], y=monthly.values, labels={"x": "Month", "y": "Average price (CAD/MWh)"}))
    chart(go.Figure(go.Heatmap(z=heatmap.values, x=[calendar.month_abbr[m] for m in heatmap.columns], y=heatmap.index,
                              colorscale="Teal", colorbar=dict(title="CAD/MWh"), hoverongaps=False,
                              hovertemplate="%{x}, hour %{y}: $%{z:.2f}/MWh<extra></extra>")).update_layout(xaxis_title="Month", yaxis_title="Hour beginning (Alberta time)", height=560))
    st.caption("Averages pool all selected years. Blank cells have no observations. Repeated autumn hours count twice; the skipped spring hour has no observation.")
else:
    events = spikes(selected)
    left, right = st.columns(2)
    left.metric("Hours above $500/MWh", f"{stats['spike_hours']:,}")
    right.metric("Share of selected hours", f"{stats['spike_percent']:.2f}%")
    if events.empty:
        st.info("No hours exceeded $500/MWh in this date range.")
    else:
        chart(px.scatter(events.sort_values("timestamp_utc"), x="timestamp_utc", y="pool_price_cad_mwh", hover_data=["timestamp_alberta", "ail_mw"], labels={"timestamp_utc": "Time (UTC; hover for Alberta time)", "pool_price_cad_mwh": "Pool price (CAD/MWh)"}))
    frequency = selected.assign(month_start=pd.to_datetime(selected.date).dt.to_period("M").astype(str), spike=selected.pool_price_cad_mwh > 500).groupby("month_start", as_index=False).agg(spike_hours=("spike", "sum"), observed_hours=("spike", "size"))
    chart(px.bar(frequency, x="month_start", y="spike_hours", hover_data=["observed_hours"], labels={"month_start": "Month", "spike_hours": "Hours above $500/MWh"}))
    st.dataframe(events[["timestamp_alberta", "pool_price_cad_mwh", "ail_mw"]].rename(columns={"timestamp_alberta": "Alberta time (UTC offset)", "pool_price_cad_mwh": "Price (CAD/MWh)", "ail_mw": "AIL (MW)"}), hide_index=True, width="stretch")
    st.caption("Strictly greater than $500/MWh. Consecutive spike hours count separately; these are hours, not distinct events.")

st.divider()
st.download_button("Download selected hourly data (CSV)", selected[data.columns[:4]].to_csv(index=False), "alberta_power_selection.csv", "text/csv")
st.caption(f"Data credit: Alberta Electric System Operator (AESO). Retrieved {metadata['retrieved_at_utc'][:10]}. Independent student portfolio project; not affiliated with AESO.")
