# FX

Rasathane'nin FX konusu (`@rasathane:295`). Her işlem günü New York kapanışından sonra kart üretir.

**Her gün**
- FX Panosu: majörler, çaprazlar, Avrupa ve gelişen ülke kurları, TL kurları ve TL sepeti, dolar endeksi. Her biri için günlük, 1 aylık ve yılbaşından beri getiri.
- Risk Panosu: riskli paralar (AUD, NZD, MXN, ZAR, BRL) ile güvenli limanların (JPY, CHF) USD karşısındaki getirisi. Risk skoru ikisinin farkı, 1 aylık değerinin son 5 yıldaki yüzdeliği de verilir.
- Sinyaller ve grafikleri: sert yükseliş/düşüş (günlük getiri 60 günlük oynaklığın 2,5 katı ve en az %0,75), 52 hafta zirvesi ve dibi, oynaklık sıçraması (1 aylık oynaklık son 5 yılın üst %5'ine girince). Bir türde 4 ve üstü sinyal varsa önce liste kartı gelir.
- Kur bağı kırılması: AUD–bakır, CAD–WTI, NOK–Brent, USD/JPY–ABD 10 yıllık. 60 günlük korelasyon 1 yıllığından 0,5 ayrılırsa grafik gelir.
- Faiz Kararı: BIS verisinde bir merkez bankasının politika faizi değişince.
- Fed Beklentisi Değişti: 30 günlük Fed fonu vadelilerinde bir ay 10 baz puandan fazla oynayınca.
- Zirve, dip, oynaklık ve bağ sinyali aynı kur için 10 işlem günü tekrarlanmaz.

**Haftanın ilk işlem günü**
- Carry Tablosu: politika faizi, ABD'ye fark, 3 aylık oynaklık ve taşıma/oynaklık oranı.
- Faiz Farkı ve Kur: ABD–Euro ve ABD–Japonya 2 yıllık tahvil faiz farkları, EUR/USD ve USD/JPY ile ilişkisi.
- Fed Beklentisi: önümüzdeki 10 ayın vadeli fiyatlarından örtük faiz.
- Kur Bağları, Kur Oynaklığı, Seanslara Göre Hareket (son 5 gün, saatlik).
- Sinyal Karnesi: geçmiş sinyallerin 5, 20 ve 60 işlem günü sonraki yönlü getirisi ve isabeti.

**Haftada bir, yeni rapor çıkınca**
- Fon Pozisyonları: CFTC TFF raporunda kaldıraçlı fonların net pozisyonu ve son 3 yıldaki yüzdeliği.

**Ayın ilk işlem günü**
- Kura Duyarlı Hisseler: en hacimli 100 BIST payında, USD/TRY'nin haftalık hareketine BIST 100'e göre en çok tepki verenler (2 yıllık veri).

## Çalıştırma

```powershell
pip install -e ..\ortak -e ..\bist -e ".[dev]"
python -m rasathane_fx --kuru
```

Kartlar `cikti/` klasörüne yazılır. Gönderim kaydı, sinyal kaydı ve son politika faizleri `veri/` altında tutulur.

## Ayarlar

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_SAHIP_ID`: depo secret'ları.
- `FX_TELEGRAM_HEDEF` (değişken): `@rasathane:295`.
- `FX_GONDER` (değişken): `1` iken gerçek gönderim.
