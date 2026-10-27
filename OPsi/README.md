# OPsi — Institutional Options Cockpit

OPsi scans option markets with free Yahoo Finance data, scores candidates with a
three-layer academic engine across four strategies (cash-secured puts, covered calls,
bull put spreads, iron condors), and presents a ranked top-5 plus a full screener in a
dark institutional-terminal dashboard.

All market data is free and **15-minute delayed**; every surface of the app carries that notice.

## How it works

1. **Scan** (`nightly`, a universe scan from the UI, or a custom symbol list) pulls
   prices and option chains from Yahoo Finance (throttled, cached in SQLite).
2. **Price** — Black-Scholes Greeks/IV are computed locally (`src/opsi/pricer.py`);
   Yahoo does not provide them.
3. **Score** — a 3-layer engine filters (liquidity, DTE, delta, earnings, capital),
   scores (annualized return, OTM probability, liquidity, IV rank, trend), and adjusts
   (skew, term-structure, earnings-jump, Kelly sizing).
4. **Serve** — the dashboard reads the latest scan from SQLite; strategy plugins make
   adding new strategies a matter of hours (`src/opsi/strategies/`).

A background worker model keeps the UI responsive: `POST /api/scan-custom` returns
HTTP 202 immediately and the header progress bar polls `GET /api/scans/active`.

## Requirements

- Python 3.11+
- pip
- Internet access for Yahoo Finance (scans only; the test suite runs offline)

No API keys, no accounts, no paid data.

## Installation

```bash
git clone <your-fork-url> opsi
cd opsi
pip install -e ../ortak -e .
```

For development (tests, lint, types):

```bash
pip install -e ../ortak -e ".[dev]"
```

This installs `yfinance`, `pandas`, `numpy`, `scipy`, `fastapi`, `uvicorn`
(plus `pytest`, `httpx`, `mypy`, `black`, `ruff` as dev extras).

## Usage

Refresh the index lists first (cached for 7 days):

```bash
python -m opsi.cli universes --refresh
```

Run a scan (S&P 500 shown; see `--universe` choices via `--help`):

```bash
python -m opsi.cli nightly --db data/opsi.db --universe sp500
```

Start the dashboard:

```bash
python -m opsi.cli serve --port 8000
```

Then open `http://localhost:8000` (redirects to `/panel`).

Run attribution for a past scan, optionally with a Black-Scholes payoff simulation:

```bash
python -m opsi.cli backtest --db data/opsi.db --scan-id 1 --strategy csp
python -m opsi.cli backtest --db data/opsi.db --sim-symbol F --sim-strike 13
```

Scan a custom CSV watchlist (see `watchlist.example.csv` — one `symbol` column):

```bash
python -m opsi.cli nightly --db data/opsi.db --watchlist watchlist.example.csv
```

### Pages

| Route        | Content                                                        |
|--------------|----------------------------------------------------------------|
| `/panel`     | Top-5 conviction cards + opportunities screener + inspector     |
| `/universes` | Ready-made index universes and thematic presets, one-click scan|
| `/lists`     | Custom watchlists (CRUD) and recent scans                      |
| `/settings`  | Scan math: thresholds, score weights, academic multipliers      |

### API (JSON)

| Endpoint                  | Notes                                                        |
|---------------------------|--------------------------------------------------------------|
| `GET /api/top5`           | Ranked top-5; falls back to latest scan with candidates       |
| `GET /api/candidates`     | Full ranked list (`scan_id`, `strategy`, `limit` params)      |
| `POST /api/scan-custom`   | Starts a background scan → HTTP 202 + `scan_id`               |
| `GET /api/scans/active`   | Live progress of the running scan (single-scan lock)          |
| `GET /api/scans`          | Recent scans with per-scan skip breakdowns                    |
| `GET /api/universes`      | Index universes with price-cache CSP expectation              |
| `GET /api/presets`        | Thematic symbol presets                                       |
| `GET/POST/DELETE /api/watchlists` | Custom symbol lists                                  |
| `GET/PUT /api/settings/params` | Scan-math set (validated, stored in DB)                   |
| `GET /api/attribution`    | Past-scan win-rate/return buckets per strategy                 |
| `GET /api/strategies`     | Registered strategy names                                     |
| `GET /api/health`         | Liveness + latest scan summary                                |

## Configuration

| Setting | Default | Notes |
|---------|---------|-------|
| `--db` / `DB_PATH` | `data/opsi.db` | SQLite file, auto-created with migrations on startup |
| `--host` / `--port` | `0.0.0.0` / `8000` | Bind `127.0.0.1` for local-only use |
| `--universe` | `all` | `all`, `stocks`, `etfs`, or an index id (`sp500`, `nasdaq100`, `dow30`, `russell2000_liquid`, `sectors`, `bist30`) |
| Scan math | built-in defaults | Tunable in `/settings`, stored in the `app_settings` table |

No environment variables or secrets are required. There is no authentication;
expose the service only on trusted networks.

## Project structure

```text
src/opsi/
  api.py          FastAPI app: pages + JSON API + background scan worker
  scan.py         Scan orchestration (universe → chains → strategies → SQLite)
  fetch.py        Throttled Yahoo Finance client + universe caches
  pricer.py       Black-Scholes Greeks/IV computed locally
  scorer.py       Layer-1 filters + layer-2 core score
  academic.py     Layer-3 academic multipliers (skew, term, jump, Kelly)
  strategies/     Plugin strategies: csp, covered_call, bull_put_spread, iron_condor
  backtest/       Attribution from accumulated scans + BS payoff simulator
  store.py        SQLite schema, migrations, writers
  params.py       Validated scan-math parameter set
  config.py       Universes, presets, thresholds, TTLs
  providers.py    Quote-provider interface (Yahoo default)
  cli.py          nightly / serve / universes / backtest commands
  schemas.py      Pydantic API contracts
static/           Dashboard (vanilla JS + CSS, no build step)
tests/            pytest suite (offline; Yahoo is mocked)
data/             Local runtime data (SQLite + caches; git-ignored, auto-created)
Dockerfile        Slim image (`python -m opsi.cli serve`)
```

## Development

```bash
python -m pytest -q
python -m ruff check src tests
python -m black --check src tests
python -m mypy src/opsi
```

Docker:

```bash
docker build -t opsi .
docker run -p 8000:8000 -v opsi-data:/app/data opsi serve
```

## Troubleshooting

- **Empty panel after a scan** — symbols above the CSP price cap ($25 default) or
  without Yahoo option chains (e.g. BIST) are skipped by design; the scan summary
  names the reason (`price-filtered`, `chainless`, `stale`). ETFs and spreads work
  on expensive underlyings.
- **A second scan returns 409** — one scan runs at a time; watch the header
  progress bar and retry when it finishes.
- **Slow first universe refresh** — index CSVs are cached for 7 days afterwards.
- **Yahoo throttling** — scans back off automatically; results accumulate in SQLite
  so re-scans are incremental.

## Rasathane Telegram kanalı (Türkçe)

OPsi her ABD işlem günü kapanıştan sonra Türkçe görsel kartlar üretip Rasathane
grubunun (`t.me/rasathane`) **OPsi** konusuna gönderir. Ücretsizdir: veri Yahoo Finance,
zamanlama GitHub Actions, gönderim Telegram Bot API.

| Gün | Kartlar (her biri ayrı mesaj) |
|---|---|
| Haftanın ilk işlem günü | IV Sarsıntısı + Haftanın 5 Nakit Teminatlı Put Hissesi ($2k–5k, $5k–15k) |
| Salı, Perşembe, Cuma | IV Sarsıntısı + Aşağı Yön Primi |
| Çarşamba | IV Sarsıntısı |

Kartlar Rasathane'nin ortak Kâğıt düzenindedir, hisse düzeyindedir, kontrat önermez; her kartta
"Yatırım tavsiyesi değildir" yazar. Mesaj metni yalnız "OPsi · Kart adı · GG.AA.YYYY" satırıdır.
Evrenin %70'inden azı okunabilirse o gün hiçbir şey gönderilmez, sahibine özel mesaj gider.

### Kurulum

1. **Grup:** Rasathane grubunda *Konular* (forum) açık olsun. "OPsi" adında bir konu açın,
   konu ayarından yalnız yöneticilerin yazmasına izin verin. Botu gruba **yönetici** ekleyin.
2. **Konu kimliği:** OPsi konusundaki herhangi bir mesaja sağ tıklayıp bağlantısını
   kopyalayın: `https://t.me/rasathane/12/345` biçimindedir, **12** konu kimliğidir.
3. **Sizin kimliğiniz** (hata mesajları için): Telegram'da `@userinfobot`'a yazın, verdiği sayı.
4. **GitHub depo ayarları** → *Secrets and variables* → *Actions*:
   - Secret `TELEGRAM_BOT_TOKEN`: BotFather'ın verdiği anahtar
   - Secret `TELEGRAM_SAHIP_ID`: 3. adımdaki sayı
   - Variable `TELEGRAM_HEDEF`: `@rasathane:12` (12 yerine kendi konu kimliğiniz)
5. **Kuru dönem:** `KANAL_GONDER` değişkeni yokken iş akışı yalnız kart üretir, göndermez
   (kartlar koşunun *Artifacts* bölümünde). En az 2 işlem günü böyle çalışsın; IV geçmişi
   birikir. Sonra Variable `KANAL_GONDER` = `1` ekleyin, gerçek gönderim başlar.
6. **Elle deneme:** *Actions* → *Kanal (Rasathane)* → *Run workflow* (kuru kutusu işaretli).

### Yerel komut

```bash
python -m opsi.cli kanal --kuru                 # bugünü üret, cikti/ klasörüne yaz
python -m opsi.cli kanal --kuru --tarih 2026-10-23  # yalnız son seans tarihi kabul edilir
python -m opsi.cli kanal                        # gönderir (TELEGRAM_* ortam değişkenleri gerekli)
python -c "from opsi.kanal.evren import evren_yenile; print(evren_yenile())"  # evreni yenile (ara sıra)
```

Kalıcı durum `kanal_veri/` klasöründedir (evren, IV geçmişi, gönderilen tarihler) ve depoda
takip edilir; Actions her koşudan sonra commit edip geri yükler.

### Yedek: bilgisayarda çalıştırma

Yahoo, GitHub sunucularından gelen istekleri engellerse aynı iş Windows Görev
Zamanlayıcı'da hafta içi 01:45'te çalıştırılabilir. **Önce GitHub'daki iş akışını kapatın**
(ikisi aynı anda çalışmamalı). Görev, depo klasöründe şunu çalıştırır (ortamda
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_HEDEF`, `TELEGRAM_SAHIP_ID` tanımlı olmalı):

```bash
git pull && python -m opsi.cli kanal && git add kanal_veri && git commit -m "veri(kanal)" && git push
```

### ETF Radarı

Opsiyon evreninden ayrı bir tarama. Nasdaq'ın listelediği bütün ABD ETF'leri (~4.000) her işlem
günü Yahoo'dan iki yıllık günlük veriyle indirilir. Son 20 günde günlük ortalama işlem tutarı
$1 milyonun altında kalanlar taranmaz. Kartlar OPsi konusuna gider (`opsi-etf.yml`, İstanbul 02:00).

| Kart | Ne zaman | İçerik |
|---|---|---|
| Yeni ETF'ler | Haftanın ilk işlem günü | Geçen haftanın başından beri listeye ilk kez giren ETF'ler |
| Yükselen Temalar | Cuma | 3 aylık getiride önde gelen 20 ETF; 1 ay ve yılbaşı getirisiyle |
| 52 Haftanın Zirvesi | Her gün | Kapanış önceki 252 günün en yükseğini bugün ilk kez aştı |
| Altın Kesişim | Her gün | SMA 50, SMA 200'ü bugün yukarı kesti |
| SMA 200'ü Yukarı Kesenler | Her gün | Önceki 20 kapanışı SMA 200'ün altındaydı, bugün üstünde |
| Hacim Patlaması | Her gün | Hacim 50 günlük ortalamanın en az 3 katı, fiyat en az %2 yukarı |

Her sinyal için bir fiyat grafiği kartı gider. Bir türde 4 ve üstü sinyal varsa önce liste kartı
gelir. Aynı ETF ve aynı tür son 20 işlem gününde gönderildiyse tekrarlanmaz.

Aynı endeksi izleyen fonlar (SPY, IVV, VOO gibi) aynı gün aynı sinyali verir. Son 126 günlük getiri
korelasyonu 0,95'i aşan ETF'lerden yalnız en likidi gösterilir.

Kaldıraçlı ve ters ETF'ler adlarından tanınır (2X, 3X, Ultra, Bull, Bear, Short, Inverse) ve
kartlarda "kaldıraçlı" etiketiyle görünür. Yükselen Temalar sıralamasına girmezler.

İlk koşu yalnız ETF listesini kaydeder; "yeni" sayılan ETF'ler ikinci koşudan sonra listeye
girenlerdir. Durum `kanal_veri/etf/` klasöründedir (ETF listesi, sinyal kaydı, gönderilenler).

```bash
python -m opsi.cli etf --kuru    # kartları cikti/etf/ klasörüne yazar, göndermez (~6 dk)
python -m opsi.cli etf           # gönderir
```

## Security

- No credentials are stored in code, config, or history; the Alpaca provider is an
  unimplemented skeleton that takes a key only as a constructor argument.
- The dashboard has no authentication — bind to `127.0.0.1` or run behind a proxy
  with auth if you expose it.
