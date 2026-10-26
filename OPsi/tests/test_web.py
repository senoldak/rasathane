import sqlite3

from fastapi.testclient import TestClient

from opsi.api import app, get_db_path


def test_index_has_delay_notice():
    c = TestClient(app)
    assert "15-min delayed" in c.get("/panel").text


def test_static_app_js_served_with_candidates():
    c = TestClient(app)
    r = c.get("/static/app.js")
    assert r.status_code == 200
    assert "candidates" in r.text
    assert "/api/top5" in r.text
    assert "sort" in r.text.lower() or "data-k" in r.text


def test_static_app_js_string_sort_uses_localecompare():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("static", "app.js")
        .read_text(encoding="utf-8")
    )
    assert "localeCompare" in text
    assert "symbol" in text and "expiry" in text


def test_candidates_fields(tmp_path):
    from opsi.store import init_db

    db = str(tmp_path / "web.db")
    init_db(db)
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO scans(started_at, status) VALUES (?, ?)", ("2026-09-08T00:00:00", "done")
    )
    sid = con.execute("SELECT id FROM scans").fetchone()[0]
    con.execute(
        "INSERT OR REPLACE INTO contracts(id,symbol,expiry,strike,right,bid,ask,volume,openInterest,iv,fetched_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("AAA|2026-10-16|10", "AAA", "2026-10-16", 10.0, "P", 0.5, 0.6, 100, 50, 0.3, "x"),
    )
    con.execute(
        "INSERT OR REPLACE INTO scores(scan_id,contract_id,score,ret_ann,prob_otm,liq,iv_rank,trend,adj,details)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (sid, "AAA|2026-10-16|10", 9.0, 0.2, 0.9, 0.5, 0.4, 0.3, 0.1, "n"),
    )
    con.commit()
    con.close()
    app.dependency_overrides[get_db_path] = lambda: db
    c = TestClient(app)
    r = c.get("/api/candidates", params={"scan_id": sid})
    assert r.status_code == 200
    item = r.json()["items"][0]
    for f in (
        "symbol",
        "strike",
        "expiry",
        "score",
        "ret_ann",
        "prob_otm",
        "liq",
        "iv_rank",
        "trend",
        "adj",
    ):
        assert f in item
    r2 = c.get("/api/top5", params={"scan_id": sid})
    assert r2.status_code == 200
    top = r2.json()["items"][0]
    for f in ("prob_otm", "liq", "iv_rank", "trend", "adj"):
        assert f in top


def test_pages_routing():
    c = TestClient(app)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/panel"
    panel = c.get("/panel").text
    assert 'aria-current="page">Panel' in panel
    assert 'id="tbl"' in panel
    assert "page-lists" not in panel
    uni = c.get("/universes").text
    assert 'aria-current="page">Universes' in uni
    assert 'id="universe-items-list"' in uni
    assert 'id="tbl"' not in uni
    lists = c.get("/lists").text
    assert 'id="watchlist-items-list"' in lists
    assert 'id="recent-scans-list"' in lists
    settings = c.get("/settings").text
    assert 'id="math-settings"' in settings
    for body in (panel, uni, lists, settings):
        assert "15-min delayed" in body
        assert "Panele D" not in body
        nav_pos = body.index('<nav class="page-nav"')
        assert nav_pos < body.index("</header>")
        assert body.index("</header>") < body.index('<footer class="terminal-footer">')


def test_panel_empty_state_names_scan_and_links_universes():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("static", "app.js")
        .read_text(encoding="utf-8")
    )
    assert "option candidates" in text
    assert 'href="/universes"' in text
    assert "currentScanInfo" in text


def test_pages_have_inline_favicon():
    c = TestClient(app)
    for path in ("/panel", "/universes", "/lists", "/settings"):
        assert 'rel="icon"' in c.get(path).text


def test_static_app_js_multipage_boot():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("static", "app.js")
        .read_text(encoding="utf-8")
    )
    assert "location.pathname" in text
    assert "showListsPage" not in text
    assert "showDashboard" not in text
    assert "view-lists" not in text


def test_style_css_has_page_nav_no_view_lists():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("static", "style.css")
        .read_text(encoding="utf-8")
    )
    assert ".page-nav" in text
    assert ".page-nav-link" in text
    assert "view-lists" not in text
    assert "btn-watchlists" not in text


def test_static_app_js_attribution_strip():
    from pathlib import Path

    text = (
        Path(__file__)
        .resolve()
        .parent.parent.joinpath("static", "app.js")
        .read_text(encoding="utf-8")
    )
    assert "/api/attribution?strategy=" in text
    assert "attribution-strip" in text
