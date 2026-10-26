# Rasathane

ABD piyasası için beş veri projesi ve bunların ortak kart kodu. Projeler her gün kamuya açık kaynaklardan veri toplar, sonuçları kart olarak Rasathane Telegram grubunun (`t.me/rasathane`) ilgili konusuna gönderir. Kartlar yatırım tavsiyesi değildir.

| Klasör | Ne yapar | Kaynak | Gönderim (İstanbul) |
|---|---|---|---|
| `biOF/` | Biyoteknoloji şirketlerinin klinik ve düzenleyici olayları (FDA tarihleri, faz sonuçları) | ClinicalTrials.gov, SEC EDGAR, Yahoo Finance | Salı–Cumartesi 09:00, ABD seansında saatte bir |
| `CAPitAL/` | Kongre üyelerinin hisse, opsiyon ve tahvil işlem beyanları | Senato ve Temsilciler Meclisi beyanları | Hafta içi 23:30 |
| `graFIX/` | S&P 500'de o gün oluşan teknik formasyonlar | Yahoo Finance | ABD kapanışından sonra |
| `INseeder/` | Şirket yöneticilerinin açık piyasa alımları (Form 4) | SEC EDGAR | Salı–Cumartesi 07:00 |
| `OPsi/` | Opsiyon piyasası taraması ve oynaklık | Yahoo Finance | Hafta içi 01:30 |
| `ortak/` | Kâğıt kart çizimi ve Telegram'a tek tek gönderim (`rasathane_ortak` paketi) | | |

Her projenin kendi README'si (graFIX'te `BENIOKU.md`) ayrıntıyı anlatır.

## Kurulum

Ortak paket önce kurulur, sonra proje. PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ortak -e "biOF[dev]"
```

graFIX ve INseeder `requirements.txt` kullanır; bu dosya ortak paketi de kurar:

```powershell
cd INseeder
pip install -r requirements.txt
```

## Testler

Her klasörde `pytest`. CI (`.github/workflows/ci.yml`) altısını ayrı işler olarak koşar.

## Zamanlanmış işler

`.github/workflows/` altında fikir başına bir iş akışı. Elle başlatılan koşu öntanımlı olarak kurudur: kartlar çizilir ve yapıt olarak yüklenir, Telegram'a gönderilmez. Gönderilen kartların kaydı her projenin veri klasörüne yazılır ve depoya commit'lenir; aynı kart iki kez gitmez.

## Marka

`marka/`: Rasathane işareti ve onu üreten betikler.
