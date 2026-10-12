"""Accessible overview story component rendered with native HTML and CSS."""
from html import escape
import math

from src.analysis import price_story


def overview_story(data, lens):
    values = price_story(data)
    spike_view = lens == "Spike influence"
    comparison = values["without_spikes"] if spike_view else values["median"]
    valid = math.isfinite(comparison)
    if spike_view:
        title = "Rare hours. A different average."
        if not values["spike_hours"]:
            title = "No spike hours in this selection."
        elif not valid:
            title = "Every selected hour exceeded $500/MWh."
        description = (f"{values['spike_hours']:,} of {values['hours']:,} hours "
                       f"({values['spike_percent']:.2f}%) exceeded $500/MWh.")
        detail = (f"Among the remaining {values['ordinary_hours']:,} hours, the average was "
                  f"${comparison:,.2f}/MWh." if valid else
                  "There are no non-spike hours to compare in this selection.")
        label = "Average excluding spikes"
        caveat = "Excluding observed spike hours is a descriptive comparison, not an estimate of prices in a market without spikes."
    else:
        title = "The average is not the typical hour."
        if math.isclose(values["mean"], comparison, abs_tol=.005):
            title = "The average and median align."
        description = f"The median is ${comparison:,.2f}/MWh. Half the selected hourly prices are at or below it."
        detail = f"The arithmetic average is ${values['mean']:,.2f}/MWh and reflects every price, including extremes."
        label = "Median hourly price"
        caveat = "Both measures use the same selected hours. The bars share a zero baseline and one scale in CAD/MWh."
    maximum = max(values["mean"], comparison if valid else 0, 1)
    ceiling = math.ceil(maximum / 10) * 10
    rows = []
    for name, number, kind in [("Average · all hours", values["mean"], "spike" if spike_view else "average"),
                               (label, comparison, "typical")]:
        available = math.isfinite(number)
        # AESO snapshot prices are nonnegative. A negative future value uses text only,
        # rather than suggesting a positive magnitude with a clipped bar.
        width = max(0, number / ceiling * 100) if available else 0
        formatted = f"${number:,.2f}" if available else "Not available"
        rows.append(f'<div class="story-row"><div class="story-row-label"><span>{escape(name)}</span>'
                    f'<strong>{formatted}</strong></div><div class="story-track" aria-hidden="true">'
                    f'<span class="story-bar story-bar--{kind}" style="width:{width:.5f}%"></span></div></div>')
    return (f'<section class="price-story" aria-label="Behind the average: {escape(lens)}">'
            f'<div class="story-copy"><h3>{escape(title)}</h3><p>{escape(description)}</p>'
            f'<p>{escape(detail)}</p></div><figure class="story-comparison">'
            + ''.join(rows) + f'<div class="story-axis" aria-hidden="true"><span>$0</span>'
            f'<span>CAD/MWh</span><span>${ceiling:,.0f}</span></div>'
            f'<figcaption>{escape(caveat)}</figcaption></figure></section>')
