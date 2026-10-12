"""Run with: streamlit run app.py."""
import calendar
from html import escape
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis import demand_bands, filter_dates, patterns, prepare, relationship, spikes, summary
from src import charts
from src.story import overview_story

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="Alberta Power | Price & Demand", page_icon=":material/bolt:", layout="wide")
st.html("<style>" + (ROOT / "assets/style.css").read_text(encoding="utf-8-sig") + "</style>")


@st.cache_data
def load_data():
    return prepare(pd.read_csv(ROOT / "data/hourly.csv"))


def chart(figure, key):
    st.plotly_chart(figure, width="stretch", theme=None, key=key,
                    config={"displayModeBar": False, "scrollZoom": False, "responsive": True})


def finding(text):
    st.html(f'<div class="finding"><p>{text}</p></div>')


def notes(items):
    st.html('<div class="notes">' + ''.join(
        f'<article class="note"><h4>{escape(title)}</h4><p>{escape(body)}</p></article>'
        for title, body in items) + '</div>')


try:
    data = load_data()
    metadata = json.loads((ROOT / "data/metadata.json").read_text())
except (OSError, ValueError, KeyError):
    st.error("The hourly data snapshot could not be loaded. Please try again later.")
    st.stop()

with st.sidebar:
    st.title("Alberta Power")
    st.caption("Wholesale electricity · AESO")
    dates = st.date_input("Date range", value=(data.date.min(), data.date.max()),
                         min_value=data.date.min(), max_value=data.date.max())
    page = st.radio("Explore", ["Overview", "Price vs. load", "Patterns", "Price spikes"])
    st.divider()
    st.caption("THE DATA")
    st.markdown(f"**{len(data):,} hourly observations**")
    st.caption(f"{metadata['start_date']} to {metadata['end_date']}\n\nHistorical snapshot · Alberta local time\n\nPrices: CAD/MWh · Actual AIL: MW")
    st.link_button("AESO data source", "https://www.aeso.ca/market/market-and-system-reporting/aeso-application-programming-interface-api/")
    st.link_button("View project on GitHub", "https://github.com/Kingjr101/alberta-power-dashboard")

st.html('<header class="masthead"><p class="kicker">Alberta electricity / Market study</p>'
        '<h1>The price of power.<br>The shape of demand.</h1>'
        '<p>Explore how demand, time of day and rare price spikes shape Alberta’s wholesale electricity market.</p></header>')
if len(dates) != 2:
    st.info("Select an end date to complete the date range.")
    st.stop()
selected = filter_dates(data, *dates)
if selected.empty:
    st.info("No observations in this date range.")
    st.stop()
stats = summary(selected)
median = selected.pool_price_cad_mwh.median()
correlation, _ = relationship(selected)
st.html(f'<div class="coverage"><span><strong>{dates[0]:%b %d, %Y} – {dates[1]:%b %d, %Y}</strong></span>'
        f'<span>{len(selected):,} observed hours</span><span>CAD/MWh · Alberta time</span></div>')
st.subheader(page)

if page == "Overview":
    for column, label, value, help_text in zip(st.columns(4),
            ["Average price", "Median price", "Maximum price", "Minimum price"],
            [stats["mean"], median, stats["max"], stats["min"]],
            ["Arithmetic mean of selected hourly prices.", "Half the selected hours cost less than this price.",
             "Highest selected hourly price.", "Lowest selected hourly price."]):
        column.metric(label, f"${value:,.2f}", help=help_text + " CAD/MWh.")

    with st.container(key="overview-story"):
        st.subheader("Behind the average")
        lens = st.radio("Choose a comparison", ["Typical prices", "Spike influence"],
                        horizontal=True, key="story_lens")
        st.html(overview_story(selected, lens))

    left, right = st.columns([2.1, 1], gap="large")
    with left, st.container(border=True):
        st.subheader("The market over time")
        st.caption("Price and demand on a shared timeline, with separate scales.")
        show_range = st.toggle("Show daily hourly-price range", value=False)
        chart(charts.market_timeline(selected, show_range), "market_timeline")
        st.caption("Daily arithmetic averages. The 7-day mean uses available days at the beginning of the selection. Load axis does not start at zero.")
    with right, st.container(border=True):
        st.subheader("What did a typical hour cost?")
        st.caption("Every selected hour, grouped by pool price.")
        chart(charts.distribution(selected), "distribution")
        below = (selected.pool_price_cad_mwh <= 50).mean() * 100
        finding(f'<strong>{below:.1f}% of hours were $50/MWh or less.</strong> '
                f'The median was ${median:,.2f}, compared with an average of ${stats["mean"]:,.2f}/MWh.')
        st.caption("Each band excludes its lower limit and includes its upper limit.")

    st.subheader("What I found")
    hourly, monthly, _ = patterns(selected)
    hour, month = int(hourly.idxmax()), int(monthly.idxmax())
    notes([
        ("A few expensive hours matter", f"Prices exceeded $500/MWh in {stats['spike_hours']:,} hours ({stats['spike_percent']:.2f}%). The average was ${stats['mean']:,.2f}/MWh; the median was ${median:,.2f}/MWh."),
        ("Timing changes the picture", f"The hour beginning {hour:02d}:00 had the highest average price (${hourly.loc[hour]:,.2f}/MWh). {calendar.month_name[month]} led the pooled monthly averages at ${monthly.loc[month]:,.2f}/MWh."),
        ("Demand is only part of the story", f"Hourly price and actual load had a Pearson correlation of {correlation:.3f}. Supply availability, fuel costs and imports are not controlled for." if pd.notna(correlation) else "Correlation is undefined when fewer than two observations vary in both price and load."),
        ("Read this as a historical study", "These findings update with the date filter. They describe association, not causation, and are not a price forecast or a retail electricity bill.")])

elif page == "Price vs. load":
    bands = demand_bands(selected)
    first, last = bands.iloc[0], bands.iloc[-1]
    a, b, c = st.columns(3)
    a.metric("Pearson correlation", f"{correlation:.3f}" if pd.notna(correlation) else "Not defined")
    b.metric("Lowest demand band · avg price", f"${first['mean']:,.2f}")
    c.metric("Highest demand band · avg price", f"${last['mean']:,.2f}")
    with st.container(border=True):
        st.subheader("Does higher demand mean higher prices?")
        st.caption("One dot per hour. Price spikes are highlighted with orange diamonds; the line is an ordinary least-squares fit.")
        chart(charts.price_load(selected), "price_load")
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.subheader("Average versus typical price")
        chart(charts.demand_comparison(selected), "demand_prices")
    with right, st.container(border=True):
        st.subheader("How often did prices spike?")
        chart(charts.demand_comparison(selected, risk=True), "demand_risk")
    if len(bands) > 1:
        finding(f'In the <strong>highest demand band</strong> ({last.load_min:,.0f}–{last.load_max:,.0f} MW), '
                f'{last.spike_percent:.2f}% of hours exceeded $500/MWh. In the lowest band '
                f'({first.load_min:,.0f}–{first.load_max:,.0f} MW), the share was {first.spike_percent:.2f}%.')
    st.caption("Bands split selected actual load into up to five quantile groups, lowest to highest. Ties stay together, so counts can differ. Hover for each band's MW range. These associations do not isolate the effect of demand.")
    with st.expander("Demand band details"):
        st.dataframe(bands.rename(columns={"band": "Demand band", "load_min": "Minimum MW", "load_max": "Maximum MW", "hours": "Observed hours", "mean": "Average CAD/MWh", "median": "Median CAD/MWh", "spike_percent": "Spike hours (%)"}), hide_index=True, width="stretch")

elif page == "Patterns":
    hourly, monthly, _ = patterns(selected)
    peak = int(hourly.idxmax())
    finding(f'The highest average price occurred in the hour beginning <strong>{peak:02d}:00 Alberta time</strong>, '
            f'at ${hourly.loc[peak]:,.2f}/MWh. Compare the average with the median to see where expensive hours pull it upward.')
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.subheader("The daily price rhythm")
        chart(charts.hourly_profile(selected), "hourly_profile")
    with right, st.container(border=True):
        st.subheader("Seasonality, year by year")
        chart(charts.monthly_profile(selected), "monthly_profile")
    with st.container(border=True):
        st.subheader("When expensive hours cluster")
        st.caption("Average pool price by month and hour. Colour moves from deep purple at lower prices to orange at higher prices.")
        chart(charts.season_heatmap(selected), "season_heatmap")
    st.caption("The heatmap and hourly profile pool all selected years. Blank cells mean no observations. Partial months include only selected dates. Both repeated autumn hours count; the skipped spring hour has no observation.")

else:
    events = spikes(selected)
    a, b, c = st.columns(3)
    a.metric("Hours above $500/MWh", f"{stats['spike_hours']:,}")
    b.metric("Share of selected hours", f"{stats['spike_percent']:.2f}%")
    c.metric("Highest selected price", f"${stats['max']:,.2f}")
    left, right = st.columns(2, gap="large")
    with left, st.container(border=True):
        st.subheader("Spike frequency by month")
        mode = st.radio("Measure", ["Share of hours", "Number of hours"], horizontal=True)
        chart(charts.spike_frequency(selected, percent=mode == "Share of hours"), "spike_frequency")
    with right, st.container(border=True):
        st.subheader("The price duration curve")
        st.caption("All selected hours ranked from highest to lowest price.")
        chart(charts.duration_curve(selected), "duration_curve")
    if events.empty:
        st.info("No hours exceeded $500/MWh in this date range.")
    else:
        with st.container(border=True):
            st.subheader("Where spikes happened")
            fig = go.Figure(go.Scatter(x=events.timestamp_utc, y=events.pool_price_cad_mwh, mode="markers",
                marker=dict(color=charts.SPIKE, size=6, opacity=.95, symbol="diamond", line=dict(color=charts.INK, width=.7)), customdata=events[["timestamp_alberta", "ail_mw"]],
                hovertemplate="%{customdata[0]}<br>$%{y:.2f}/MWh · %{customdata[1]:,.0f} MW<extra></extra>"))
            fig.update_xaxes(title="Time (UTC; hover for Alberta time)")
            fig.update_yaxes(title="Price (CAD/MWh)")
            chart(charts.style(fig, 320), "spike_timeline")
        st.subheader("Inspect the spike hours")
        st.dataframe(events[["timestamp_alberta", "pool_price_cad_mwh", "ail_mw"]].rename(columns={"timestamp_alberta": "Alberta time (UTC offset)", "pool_price_cad_mwh": "Price (CAD/MWh)", "ail_mw": "AIL (MW)"}), hide_index=True, width="stretch", height=300)
    st.caption("Strictly greater than $500/MWh. Consecutive hours count separately. Monthly percentages use observed hours in your selection, including partial months.")

st.divider()
with st.expander("About the data & methodology"):
    st.markdown("**Source:** AESO Pool Price Report and Actual Forecast Report, using actual Alberta Internal Load (AIL). "
                "UTC timestamps are joined one-to-one; charts use Alberta time unless labelled otherwise. "
                "The snapshot contains no missing UTC hours. No interpolation, forecast substitution or spike removal is applied.")
    st.markdown("**Interpretation:** Prices are unweighted hourly settlement prices in CAD/MWh. AIL is measured in MW. "
                "Correlation and demand bands describe association, not causation. Wholesale prices are not retail electricity bills.")
    st.caption(f"Retrieved {metadata['retrieved_at_utc'][:10]}. The committed snapshot makes the app reproducible without an API key.")
st.download_button("Download selected hourly data", selected[data.columns[:4]].to_csv(index=False), "alberta_power_selection.csv", "text/csv")
st.caption("Data: Alberta Electric System Operator (AESO). Independent student portfolio project; not affiliated with AESO.")
