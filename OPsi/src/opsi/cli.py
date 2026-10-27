# src/opsi/cli.py
"""Command line: `python -m opsi.cli [serve|nightly|backtest|kanal]`."""

import argparse
import json
import os
import sys

from .backtest import run_attribution, simulate_strategy
from .config import DB_PATH, UNIVERSES
from .fetch import get_history
from .logging import setup_logging
from .scan import run_full_scan, run_snapshot
from .store import init_db


def cmd_nightly(
    db: str = DB_PATH,
    snapshot_only: bool = False,
    watchlist: str | None = None,
    universe: str = "all",
    params_file: str | None = None,
) -> int:
    """Nightly full scan: prepare DB, scan, print scan_id."""
    import json

    setup_logging()
    init_db(db)
    params = None
    if params_file:
        from .params import normalize_params

        with open(params_file, encoding="utf-8") as f:
            params = normalize_params(json.load(f))
    if snapshot_only:
        if watchlist is None:
            print("snapshot rows:", run_snapshot(db))
        else:
            print("snapshot rows:", run_snapshot(db, watchlist=watchlist))
        return 0
    if watchlist is None:
        scan_id = run_full_scan(db, universe=universe, params=params)
    else:
        scan_id = run_full_scan(db, watchlist=watchlist, universe=universe, params=params)
    print(f"scan_id: {scan_id}")
    return 0


def cmd_universes(refresh: bool = False) -> int:
    """List ready-made universes; cache them with --refresh (one by one, throttled)."""
    import sys

    from .fetch import get_universe_symbols, universe_info

    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except ValueError:
            pass
    for uid in sorted(UNIVERSES):
        try:
            syms = get_universe_symbols(uid) if refresh else None
            info = universe_info(uid)
            n = len(syms) if syms is not None else info["count"]
            print(f"{uid:22s} {n!s:>5s}  {info['title']}")
        except Exception as e:
            print(f"{uid:22s} ERROR: {e}")
            return 1
    return 0


def cmd_serve(host: str = "0.0.0.0", port: int = 8000) -> int:
    """Dashboard API service."""
    setup_logging()
    import uvicorn

    uvicorn.run("opsi.api:app", host=host, port=port)
    return 0


def cmd_backtest(
    db: str = DB_PATH,
    scan_id: int | None = None,
    strategy: str | None = None,
    score_min: float = 0.0,
    sim_symbol: str | None = None,
    sim_strike: float = 0.0,
) -> int:
    """Run attribution (+ optional BS simulation), print JSON summary."""
    from .strategies import STRATEGIES

    setup_logging()
    init_db(db)
    out: dict[str, object] = {}
    if scan_id is not None:
        import sqlite3

        run_id = run_attribution(db, scan_id, strategy, score_min)
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM backtest_runs WHERE id=?", (run_id,)).fetchone()
        con.close()
        out["attribution"] = dict(row) if row else {"run_id": run_id}
    if sim_symbol is not None and sim_strike > 0:
        strat = strategy or "csp"
        if strat not in STRATEGIES:
            print(f"unknown strategy: {strat}")
            return 2
        closes = get_history(sim_symbol)
        out["simulation"] = simulate_strategy(sim_symbol, strat, closes, sim_strike)
    print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_kanal(kuru: bool = False, tarih: str | None = None) -> int:
    """Rasathane Telegram kartları: günlük akış (kuru: üret, gönderme)."""
    if not kuru and not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_HEDEF")):
        print("TELEGRAM_BOT_TOKEN ve TELEGRAM_HEDEF gerekli (ya da --kuru)", file=sys.stderr)
        return 2
    setup_logging()
    from .kanal import calistir as kanal

    try:
        sonuc = kanal.calistir(kuru=kuru, tarih=tarih, grafik_fiyat=get_history)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(sonuc, ensure_ascii=False))
    return 1 if sonuc["durum"] in ("spy_yok", "eksik_veri") else 0


def cmd_etf(kuru: bool = False, tarih: str | None = None) -> int:
    """ETF Radarı kartları: yeni ETF'ler, yükselen temalar, günlük sinyaller (kuru: üret, gönderme)."""
    if not kuru and not (os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_HEDEF")):
        print("TELEGRAM_BOT_TOKEN ve TELEGRAM_HEDEF gerekli (ya da --kuru)", file=sys.stderr)
        return 2
    setup_logging()
    from .etf import calistir as etf

    try:
        sonuc = etf.calistir(kuru=kuru, tarih=tarih)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(sonuc, ensure_ascii=False))
    return 1 if sonuc["durum"] in ("spy_yok", "eksik_veri") else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opsi", description="OPsi options scanner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_nightly = sub.add_parser("nightly", help="run full scan")
    p_nightly.add_argument("--db", default=DB_PATH)
    p_nightly.add_argument("--snapshot-only", action="store_true")
    p_nightly.add_argument("--watchlist", default=None)
    p_nightly.add_argument(
        "--universe",
        default="all",
        choices=["all", "stocks", "etfs", *sorted(UNIVERSES)],
        help="universe to scan (all, stocks, etfs + ready-made indexes)",
    )
    p_nightly.add_argument(
        "--params-file",
        default=None,
        help="scan math JSON file (active DB set if omitted)",
    )
    p_serve = sub.add_parser("serve", help="dashboard service")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_uni = sub.add_parser("universes", help="list / cache ready-made index universes")
    p_uni.add_argument("--refresh", action="store_true", help="refresh lists and write to cache")
    p_bt = sub.add_parser("backtest", help="past scan attribution + simulation")
    p_bt.add_argument("--db", default=DB_PATH)
    p_bt.add_argument("--scan-id", type=int, default=None)
    p_bt.add_argument("--strategy", default=None)
    p_bt.add_argument("--score-min", type=float, default=0.0)
    p_bt.add_argument("--sim-symbol", default=None)
    p_bt.add_argument("--sim-strike", type=float, default=0.0)
    p_kanal = sub.add_parser("kanal", help="Rasathane Telegram kartları (günlük)")
    p_kanal.add_argument("--kuru", action="store_true", help="kartları üret, gönderme")
    p_kanal.add_argument("--tarih", default=None, help="YYYY-AA-GG (işlem günü kontrolünü atlar)")
    p_etf = sub.add_parser("etf", help="ETF Radarı kartları (günlük)")
    p_etf.add_argument("--kuru", action="store_true", help="kartları üret, gönderme")
    p_etf.add_argument(
        "--tarih", default=None, help="YYYY-AA-GG (son seans; işlem günü kontrolünü atlar)"
    )
    args = parser.parse_args(argv)
    if args.cmd == "nightly":
        return cmd_nightly(
            args.db,
            args.snapshot_only,
            args.watchlist,
            universe=args.universe,
            params_file=args.params_file,
        )
    if args.cmd == "kanal":
        return cmd_kanal(args.kuru, args.tarih)
    if args.cmd == "etf":
        return cmd_etf(args.kuru, args.tarih)
    if args.cmd == "universes":
        return cmd_universes(refresh=args.refresh)
    if args.cmd == "backtest":
        return cmd_backtest(
            args.db, args.scan_id, args.strategy, args.score_min, args.sim_symbol, args.sim_strike
        )
    return cmd_serve(args.host, args.port)


if __name__ == "__main__":
    sys.exit(main())
