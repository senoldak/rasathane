from pathlib import Path

def test_static_assets_exist():
    static_dir = Path("capitolseeder/static")
    assert (static_dir / "index.html").exists()
    assert (static_dir / "css" / "terminal.css").exists()
    assert (static_dir / "js" / "app.js").exists()
    assert (static_dir / "js" / "charts.js").exists()
    assert (static_dir / "js" / "ocr_viewer.js").exists()
    
    content = (static_dir / "index.html").read_text(encoding="utf-8")
    assert "CAPitAL" in content
    assert "terminal.css" in content
    assert "ptr-ticker" in content
    assert "conflict-matrix" in content
    assert "portfolio-chart" in content
    assert "ocr-modal" in content
    assert "live-stream-status-pill" in content
    assert "btn-sync-feed" in content

    css_content = (static_dir / "css" / "terminal.css").read_text(encoding="utf-8")
    assert "livePulseRow" in css_content
    assert "new-live-row" in css_content
