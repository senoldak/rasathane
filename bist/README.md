# bist

Borsa İstanbul VİOP (vadeli işlem ve opsiyon) ve varant piyasası veri kütüphanesi ve Rasathane site verisi dışa aktarımı.

## Kapsam

- **VİOP bülteni (`rasathane_bist/viop.py`):** Borsa İstanbul günlük VİOP bültenini (`viop_YYYYMMDD.csv`) ayrıştırır, sözleşme kodlarını ve dayanak varlıkları çözer.
- **Pay bülteni ve varantlar (`rasathane_bist/bulten.py`, `varant_adi.py`, `opsiyon.py`):** BIST pay bültenindeki varantları çözümler, Black-Scholes örtük oynaklık ve etkin kaldıraç hesaplar.
- **Geçmiş birikimi (`rasathane_bist/gecmis.py`):** Geriye dönük bültenleri indirip dayanak bazında uzlaşma, ön vade, açık pozisyon ve put/call hacimlerini `veri/viop-gunluk.json` dosyasında biriktirir (vade sıçramalarını önlemek için oranlama ile geriye uyarlama).
- **Site verisi dışa aktarımı (`rasathane_bist/site_aktar.py`, `site_ek.py`):** `site-veri/viop/` klasörüne finfolis Astro sitesi için sayfalar ve grafik serileri üretir:
  - `vadeli.json`: Vadeli işlem sözleşmeleri (hacim sıralı).
  - `on-vade.json`: Dayanak bazında ön vade fiyatları, EMA 144/233/377 ve RSI 14 serileri.
  - `acik-pozisyon.json`: Vadeli açık pozisyon değişimleri ve geçmiş serileri.
  - `put-call.json`: Dayanak bazlı put/call oranları ve serileri.
  - `takvim.json`: Gelecek vade tarihleri ve açık pozisyon yoğunluğu.
  - `vade-egrisi.json`: Vade eğrileri.
  - `varant.json`: Pay bülteni varantları ve etkin kaldıraç tablosu.

## Kurulum ve Test

```powershell
pip install -e ..\ortak -e ".[dev]" ruff black mypy
pytest -q
ruff check rasathane_bist tests
black -l 100 --check rasathane_bist tests
MYPYPATH=..\ortak mypy --strict rasathane_bist
```

## Çalıştırma

```powershell
python -m rasathane_bist --site ..\site-veri [--faiz 0.358646]
```
