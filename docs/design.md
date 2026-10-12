# Dashboard design notes

This is an analytical portfolio project for energy internship recruiters. The redesign keeps the Python / Streamlit / Plotly stack and the four original pages, with a light surface, a consistent teal accent, dark text, and amber reserved for price spikes and highlighted observations. Motion is limited to normal control feedback; the data stays still while readers inspect it.

## References and scope

- [Awesome Dataviz](https://github.com/hal9ai/awesome-dataviz) is a catalog, not an installable dashboard theme. Its Plotly entry supports using the project's existing plotting library. The redesign uses standard time-series, distribution, heatmap and price-duration views; no code is copied from the catalog.
- [Taste skill](https://github.com/Leonxlnx/taste-skill), installed locally as `design-taste-frontend`, explicitly excludes dashboards in its current version. Its brief-first, restrained presentation guidance informs the introductory header. Its React defaults and animation prescriptions are not runtime dependencies and do not override the requested Streamlit stack.
- The implementation is custom Streamlit styling, not an official Carbon, Fluent or other design-system implementation.

## What changed and why

- A clearer introductory header and coverage line establish the question and date scope.
- Average and median appear together because rare high prices pull the average above a typical hour.
- Aligned price and demand plots share time, with independent labelled vertical scales rather than a dual-axis overlay. A range toggle reveals within-day extremes. The load axis is explicitly labelled as not starting at zero.
- The price distribution includes every hour. Fixed, right-inclusive bins keep exactly $500 out of the spike band.
- Demand quantile bands compare mean, median and spike percentage; ties remain together, with denominators available in a detail table.
- Monthly price charts separate years, while the heatmap pools only selected observations. Missing observations remain blank, not zero.
- Spike frequency defaults to a percentage, so month length and partial selections have explicit denominators. A price-duration curve shows the whole tail without dropping extremes.
- The CSS uses stable Streamlit data-test selectors instead of generated class names. Charts, columns and notes stack on narrow screens. All chart colors are set explicitly with `theme=None` to prevent Streamlit from replacing them.

Validation: pytest includes pure-analysis cases, data integrity checks and a real-data Streamlit AppTest for all pages and date-filter edge cases. Playwright is used locally to check rendering and controls at desktop and phone widths; it is not a production dependency.
