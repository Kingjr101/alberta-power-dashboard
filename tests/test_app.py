"""Smoke-test each real-data page and filter states without a web server."""
from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_pages_and_filters():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=30).run()
    app.radio(key="story_lens").set_value("Spike influence").run()
    assert not app.exception
    app.radio(key="story_lens").set_value("Typical prices").run()
    for page in ["Overview", "Price vs. load", "Patterns", "Price spikes"]:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, [error.message for error in app.exception]
    app.sidebar.date_input[0].set_value((date(2025, 1, 1), date(2025, 1, 1))).run()
    assert not app.exception
    assert app.info[0].value.startswith("No hours exceeded")
    app.sidebar.date_input[0].set_value((date(2025, 1, 1),)).run()
    assert not app.exception
    assert app.info[0].value.startswith("Select an end date")
