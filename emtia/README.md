# Emtia

Rasathane'nin emtia konusu (`@rasathane:281`). Her ABD işlem günü vadeli kapanışlarından sonra kart üretir.

**Her gün**
- Emtia Panosu: 20 emtianın ön ay vadeli fiyatı, günlük, 1 aylık ve yılbaşından beri getirisi; gram altın, USD/TRY, dolar endeksi.
- Emtia Oranları: altın/gümüş, bakır/altın, Brent/doğalgaz, Brent/WTI ve son 5 yıldaki yüzdelikleri.
- Sinyaller ve grafikleri: sert yükseliş/düşüş (günlük getiri 60 günlük oynaklığın 2,5 katı ve en az %2), 52 hafta zirvesi ve dibi, uç dilimdeki oran (5 yılın alt/üst %5'i), gram altında 5 yılın zirvesi. Bir türde 4 ve üstü sinyal varsa önce liste kartı gelir. Zirve, dip, oran ve gram altın sinyali aynı emtia için 10 işlem günü tekrarlanmaz.

**Haftada bir**
- Haftanın Veri Takvimi (haftanın ilk işlem günü).
- EIA Petrol Stokları ve EIA Doğalgaz Depoları: yeni rapor haftası yayımlanınca.
- Fon Pozisyonları: CFTC raporundaki managed money net pozisyonu, son 3 yıldaki yüzdeliği.

## Çalıştırma

```powershell
pip install -e ..\ortak -e ".[dev]"
python -m rasathane_emtia --kuru
```

Kartlar `cikti/` klasörüne yazılır. Gönderim kaydı ve rapor durumu `veri/` altında tutulur.

## Ayarlar

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_SAHIP_ID`: depo secret'ları.
- `EMTIA_TELEGRAM_HEDEF` (değişken): `@rasathane:281`.
- `EMTIA_GONDER` (değişken): `1` iken gerçek gönderim.
- `EIA_API_KEY` (isteğe bağlı secret): yoksa EIA'nın `DEMO_KEY`'i kullanılır.
