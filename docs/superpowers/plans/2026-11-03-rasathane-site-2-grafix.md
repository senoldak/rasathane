# Rasathane sitesi, Plan 2: graFİX — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** graFİX'in (S&P 500 teknik taraması) bugünkü formasyonlarını ve her hissenin fiyat + gösterge grafiğini `finfolis.com/rasathane/grafix/` altında sunmak. Kod `senoldak/rasathane-ic` içinde gizli kalır; yalnız sonuç verisi açık `senoldak/rasathane` deposuna yazılır.

**Architecture:** graFİX koşusu, kart çizip gönderdikten sonra iki çıktı üretir: `site-veri/grafix/formasyonlar.json` (bugünkü sinyal tablosu) ve `site-veri/grafix/seri/<sembol>.json` (her hisse için son 252 işlem günü: kapanış, EMA 233, EMA 377, SMA 200, günlük Kijun, haftalık Kijun). Koşu sonunda iş akışı, açık depoyu ayrı bir klasöre çekip yalnız `site-veri/grafix/` yollarını commit eder ve yükler. finfolis'in prebuild'i (Plan 1, Task 4) bu veriyi `public/rasathane/veri/` altına koyar; sayfalar Plan 1'deki şablonla kurulur.

**Tech Stack:** Python 3.12 (graFİX mevcut yığını: pandas, numpy, yfinance, httpx); `rasathane_ortak.site` (Plan 1, Task 2); finfolis Astro + lightweight-charts 5 (Plan 1, Task 6).

**Spec:** `docs/superpowers/specs/2026-11-03-rasathane-site-design.md`, bölüm "graFİX bölümü".

**İki repo:**
- `senoldak/rasathane-ic` (gizli): `graFIX/grafix/`, `.github/workflows/grafix.yml`. Yerel yolu: önce `gh repo clone senoldak/rasathane-ic "$TEMP/rasathane-ic"` ile ayrı bir klasöre alınır; bu oturumun başka klasörlerine dokunulmaz.
- `senoldak/rasathane` (açık): `ortak/` ve `site-veri/`. Yerel yolu: `C:\DEPO\KOD DEPOSU\para\rasathane`.
- finfolis: `C:\DEPO\KOD DEPOSU\mecmua\finfolis` (Task 6).

**Ön koşul:** Plan 1'in Task 2 (ortak `site.py`) ve Task 4 (prebuild) değişiklikleri **push edilmiş** olmalı. graFİX, `rasathane_ortak`'ı kendi `requirements.txt`'inden kurarsa, bu değişikliğin uzak depoda görünmesi gerekir. Task 0 bunu kontrol eder.

## Global Constraints

- Maliyet sıfır: yeni sunucu, D1/KV, ücretli plan yok.
- Kod gizli kalır: `rasathane-ic`'teki hiçbir kod, dosya adı ya da yapılandırma açık depoya kopyalanmaz. Açık depoya yalnız `site-veri/grafix/` altındaki JSON yazılır.
- Site metni: "sinyal" sözcüğü yok; formasyon ve kesişim dili kullanılır. "al", "sat", "öneri", "fırsat" yok. Her sayfada "Yatırım tavsiyesi değildir. Veriler gecikmelidir." ve Yahoo Finance kaynağı.
- Sayı biçimi Türkçe (virgül ondalık, nokta binlik); tarih İstanbul saatiyle.
- Her grafik etkileşimli (yakınlaştırma, imleç değeri); finfolis'in grafik denetimi ve TradingView atfı geçerli.
- Açık depoya yazan token en az yetkiyle tanımlanır: yalnız `senoldak/rasathane`, yalnız içerik yazma. Token'ı açmak ve sır olarak eklemek sahibin adımıdır; plan bunu komut ve ekran adımlarıyla verir.
- Commit'lerde yalnız değişen dosyalar; `git add` yalnız var olan yollara.

## Review Focus

1. **Yahoo verisi eksik** (bazı semboller boş): o hisse sayfası atlanır ya da son iyi veriyle kalır; formasyon tablosu yine yayımlanır; koşu sahibe bildirir (mevcut graFİX davranışı). → Task 2 testi.
2. **Hisse yeni listeye girdi, geçmişi kısa** (400 satırdan az): grafik çizilmez, sayfa "Yeterli geçmiş yok" der. → Task 2 testi.
3. **Çift sınıf hisseler** (GOOG/GOOGL, BRK-B): sembol dosya adı güvenli biçime çevrilir (`BRK-B` → `BRK-B`, `BF.B` → `BF.B`; izin verilen karakterler dışında olmaz) ve iki sınıf da ayrı sayfa alır; URL'de büyük harf kullanılır. → Task 2 testi.
4. **Koşu iki kez çalışırsa** (cron + vesaire): aynı günün verisi ikinci kez yazılır ama commit yalnız gerçek fark varsa yapılır; iki koşu aynı anda push etmez (`concurrency`). → Task 4 testi.
5. **Kuru koşu açık depoya yazmaz:** yalnız `--site` ve kuru=false iken site yazılır; elle kuru koşu açık depoya dokunmaz. → Task 3 testi.

---

### Task 0: Ön kontroller ve sahip kapısı

- [ ] **Step 1: Bağımlılık.** `rasathane-ic/graFIX/requirements.txt` içinde `rasathane-ortak`'ın nereden kurulduğuna bak (git URL'si, yerel yol ya da PyPI). Git URL'si ise açık depodaki `main` hedefli kurulum Task 2'nin push'una bağlıdır.
- [ ] **Step 2: Boyut ölçümü.** Yerelde bir tam graFİX kuru koşusundan sonra (Task 3 bitince) `site-veri/grafix/` klasörünün toplam boyutunu ölç. Bu sayı Task 4'ün kararını verir (aşağıda).
- [ ] **Step 3: Sahip kapısı — token.** Sahibi, `senoldak/rasathane` için içerik yazma yetkili, yalnız bu depoya bağlı bir fine-grained token açar, `rasathane-ic` Actions sırlarına `RASATHANE_YAZ_TOKEN` olarak ekler. Token açılmadan Task 4 başlamaz. (`vesaire`'nin `GITHUB_TOKEN`'ı bunun yerine kullanılmaz: kapsamı sahibin onayına bağlı, geniş.)

### Task 1: Ortak çok-seri yazıcısı (rasathane, açık)

**Files:**
- Modify: `ortak/rasathane_ortak/site.py`
- Modify: `ortak/tests/test_site.py`

**Interfaces:**
- Consumes: Plan 1 Task 2'deki `seri_yaz`, `_ad_kontrol`, `_yaz_json` yardımcıları (aynı dosyada).
- Produces: `def seri_cok_yaz(kok: Path, bolum: str, anahtar: str, tarihler: Sequence[date], sutunlar: Mapping[str, Sequence[float | None]], *, ad: str, birim: str, isaretler: Sequence[tuple[date, str]] = ()) -> Path` — `kok/bolum/seri/<anahtar>.json` yazar: `{"sema":1,"ad","birim","tarihler":["YYYY-AA-GG",...],"sutunlar":{"kapanis":[...],"ema233":[...],...},"isaretler":[["YYYY-AA-GG","metin"],...]}`. `sutunlar` değerleri aynı uzunlukta olmalı; `None`/NaN → `null`. Sütun adları `^[a-z0-9_]{1,30}$`.

- [ ] **Step 1: Başarısız testler:** uzunluk uyuşmazlığında `ValueError`; NaN → `null`; sütun adı `"EMA 233"` gibi geçersizse `ValueError`; çıktıda `tarihler` ile `sutunlar` aynı uzunlukta.
- [ ] **Step 2:** `cd ortak; python -m pytest tests/test_site.py -q` → FAIL.
- [ ] **Step 3: Uygula** (`_yaz_json` ile tek atomik yazım).
- [ ] **Step 4:** `python -m pytest -q` → PASS.
- [ ] **Step 5:** Commit: `git commit -m "Ortak: çok sütunlu seri yazıcısı`n`nCo-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>" -- ortak/rasathane_ortak/site.py ortak/tests/test_site.py`. Push, Task 0 Step 1'in gereği.

### Task 2: graFİX dışa aktarıcısı (rasathane-ic, gizli)

**Files (rasathane-ic klonunda):**
- Create: `graFIX/grafix/site_aktar.py`
- Modify: `graFIX/grafix/calistir.py` (`Ayarlar.site: Optional[Path] = None`; sinyaller hesaplandıktan sonra, `if not planlar` dalından ÖNCE çağrılır)
- Test: `graFIX/tests/test_site_aktar.py`

**Interfaces:**
- Consumes: `grafix.gostergeler` (`ema`, `sma`, `kijun`, `haftalik`), `grafix.model.Sinyal` (`tur`, `sembol`, `gun`, `kapanis`, `seviye`, `alt_bilgi`), `grafix.model.TURLER` (`kod`, `ad`), `rasathane_ortak.site` (`sayfa_yaz`, `seri_cok_yaz`, `Sutun`, `Kaynak`).
- Produces:
  - `def aktar(kok: Path, simdi: datetime, bugun: date, veriler: dict[str, pd.DataFrame], evren: Sequence[Hisse], sinyaller: Sequence[Sinyal]) -> list[Path]`
  - `formasyonlar` sayfası (`kok/grafix/formasyonlar.json`): satırlar `{tur, tur_ad, sembol, sirket, kapanis, seviye, alt_bilgi, seri}`. Süzgeç: `tur` (TURLER'in `ad`'ı). Sütunlar: `tur_ad` (metin), `sembol` (metin), `sirket` (metin), `kapanis` (sayi, 2), `seviye` (sayi, 2), `alt_bilgi` (metin).
  - Seri dosyaları: her evren hissesi için son 252 işlem günü; sütunlar `kapanis`, `ema233`, `ema377`, `sma200`, `kijun_g`, `kijun_h` (haftalık Kijun günlüğe `ffill` ile yayılır). Yeterli geçmiş yoksa (`len < 400`) seri yazılmaz ve sayfa bunu gösterir (satırda `seri: null`).
  - Sembol anahtarı: Yahoo biçimi (`BRK-B`), `seri_cok_yaz` regex'ine uyar; uymayan sembol atlanır ve günlüğe yazılır.
  - Kaynaklar: `Kaynak("Yahoo Finance", "https://finance.yahoo.com/")`, `Kaynak("S&P 500 listesi, Wikipedia", "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")`.

- [ ] **Step 1: Başarısız testler:**
  - `test_formasyon_sayfasi`: iki sinyalli sahte veriyle `formasyonlar.json` satır sayısı 2, `tur_ad` Türkçe ad.
  - `test_seri_252_gun_ve_gosterge`: 600 günlük sahte fiyatla `seri/AAPL.json` 252 tarih, `ema233` ilk 232 değer `null`.
  - `test_kisa_gecmis_seri_yok`: 300 günlük hisse için seri dosyası yok, formasyon satırında `seri: null`.
  - `test_sembol_guvenli`: `BRK-B` yazılır, `BAD SYM!` atlanır.
  - `test_metinde_yasak_sozcuk_yok`: çıktı JSON'larında `\b(al|sat|sinyal|öneri|fırsat)\b` yok.
- [ ] **Step 2:** `cd graFIX; python -m pytest tests/test_site_aktar.py -q` → FAIL.
- [ ] **Step 3: Uygula.** `haftalik` ile `kijun_h` hesabı; `kijun` günlük. Sayılar 2 ondalığa yuvarlanır (`round(x, 2)`), böylece dosya boyutu sınırlı kalır.
- [ ] **Step 4:** `python -m pytest -q` (graFİX) ve `python -m ruff check grafix tests` → temiz.
- [ ] **Step 5:** `calistir.py` değişikliğini ekle; mevcut testler (varsa) PASS.
- [ ] **Step 6:** Commit (rasathane-ic'te): `git commit -m "graFİX: site verisi dışa aktarımı`n`nCo-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"`. Push rasathane-ic'e, yalnız bu iki dosya ve test.

### Task 3: İş akışı: açık depoya yazma (rasathane-ic, grafix.yml)

**Files:**
- Modify: `.github/workflows/grafix.yml` (rasathane-ic)

- [ ] **Step 1:** İlk adımda açık depoyu klonla: `actions/checkout@v5` with `repository: senoldak/rasathane`, `token: ${{ secrets.RASATHANE_YAZ_TOKEN }}`, `path: public`, `ref: main`. Yalnız sığ klon (`fetch-depth: 1`).
- [ ] **Step 2:** Koşu adımına `--site ../public/site-veri` eklenir; yalnız `kuru != true` ve `zorla != true` iken (`SITE` ortam değişkeni `1`).
- [ ] **Step 3:** Kayıt adımından önce açık depoda `git add site-veri/grafix` (varsa), yalnız gerçek fark varsa commit (`git diff --cached --quiet` kontrolü), `git pull --rebase && git push` döngüsü (üç deneme). Commit mesajı: `graFİX: site verisi $(date -u +%F)`. Commit'i `github-actions[bot]` değil, token sahibi için yapılandırılmış kimlik kullanır.
- [ ] **Step 4:** YAML'ı `actionlint` ile (yoksa `python -c "import yaml; yaml.safe_load(open(...))"`) doğrula.
- [ ] **Step 5:** Commit ve push (rasathane-ic). **Elle çalıştırma yok**; ilk gerçek koşu sahibin onayıyla yapılır.

### Task 4: Yazma yetkisi ve boyut kapısı

- [ ] **Step 1:** Task 0 Step 3 tamamlandığını sahip onaylar.
- [ ] **Step 2: Boyut kararı.** Task 0 Step 2'de ölçülen `site-veri/grafix/` boyutu günlük commit olarak sınanır: günlük sıkıştırılmış artış 1 MB'ı aşarsa, seri dosyalarının açık depodaki `main`'de tutulması yerine **ayrı bir yetim (orphan) dal** (`site-veri`) kullanılır, her gün zorla yazılır (geçmiş tutulmaz). finfolis prebuild bu dala `--depth 1` ile klonlar. Karar sahibin onayıyla verilir; plan iki yolu da karşılar (Task 2 yazıcısı aynı, yalnız hedef dal değişir).
- [ ] **Step 3:** Karar notu `docs/superpowers/specs/` altına eklenir.

### Task 5: finfolis: graFİX sayfaları (finfolis)

**Files (finfolis):**
- Modify: `src/lib/rasathane/bolumler.mjs` (`grafix` bölümü: ad "Teknik tarama")
- Modify: `src/pages/rasathane/[bolum]/index.astro`, `src/pages/rasathane/[bolum]/[sayfa].astro` (grafix formasyon tablosu)
- Create: `src/pages/rasathane/grafix/[sembol]/index.astro` (hisse sayfası)
- Modify: `src/components/rasathane/Grafik.astro` (çok seri: kapanış + seçilebilir göstergeler; onay kutuları)
- Test: `src/lib/rasathane/grafix.test.mjs` (gösterge seçimi ve "yeterli geçmiş yok" kararı)

**Interfaces:**
- Consumes: Plan 1'in `sayfalariOku`, `Tablo.astro`, `suz`/`sirala`; `seri/<sembol>.json` (`sutunlar` ve `tarihler`).
- Produces:
  - `gostergeSecimi(sutunlar, secili: string[]) → string[]`: `kapanis` her zaman, diğerleri seçime göre.
  - `yeterliGecmis(seri): boolean` (en az 252 nokta).

- [ ] **Step 1: Başarısız test** (`grafix.test.mjs`): `gostergeSecimi` kapanışı her zaman döndürür; `yeterliGecmis` 251 ve 252 noktada doğru sonucu verir.
- [ ] **Step 2:** `npm run test:site` → FAIL. **Step 3:** Uygula.
- [ ] **Step 4:** Formasyon sayfası Plan 1'deki tablo bileşenini kullanır: süzgeç `tur_ad`, sıralama `kapanis` ve `seviye`; satır tıklaması `/rasathane/grafix/<sembol>/` adresine gider.
- [ ] **Step 5:** Hisse sayfası: başlık (sembol + şirket), `formasyonlar`'daki bugünkü satırları (varsa), grafik (kapanış + göstergeler), kaynaklar, uyarı, TradingView atfı. Geçmiş yoksa "Yeterli geçmiş yok" yazısı.
- [ ] **Step 6:** `npm run build`; 500 hisse sayfası derlenir; `dist/rasathane/grafix/` altında sayfa sayısı doğru.
- [ ] **Step 7:** Tarayıcıda: formasyon tablosunda süzme, bir hisseye tıklayıp göstergeleri açıp kapatma, 375 px'te yatay kayma yok. Ekran görüntüsü sahibine.
- [ ] **Step 8:** Commit (yalnız bu dosyalar): `git commit -m "Rasathane: graFİX sayfaları ve çok seri grafik`n`nCo-Authored-By: Claude Haiku 5.5 <noreply@anthropic.com>"`.

### Task 6: Canlı doğrulama ve sahip onayı

- [ ] **Step 1:** Sahip, `RASATHANE_YAZ_TOKEN`'ı tanımladıktan sonra graFİX iş akışını **kuru değil ama zorla değil** şekilde elle çalıştırmasını onaylar. (Ya da bir sonraki zamanlanmış koşuyu bekler.)
- [ ] **Step 2:** `senoldak/rasathane`'de `site-veri/grafix/formasyonlar.json` ve `seri/` oluştuğunu doğrula (`gh api repos/senoldak/rasathane/contents/site-veri/grafix`).
- [ ] **Step 3:** finfolis'in bir sonraki derlemesinden sonra `https://finfolis.com/rasathane/grafix/` ve bir hisse sayfası (örn. `/rasathane/grafix/AAPL/`) 200 döner; grafik yüklenir.
- [ ] **Step 4:** finfolis ana sayfası ve bir haber sayfası eskisi gibi.
- [ ] **Step 5:** Bu planın bittiği notu hafızaya eklenir (`rasathane-site` memory).
