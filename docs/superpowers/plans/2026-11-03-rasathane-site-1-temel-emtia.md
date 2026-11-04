# Rasathane sitesi, Plan 1: temel + emtia — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `finfolis.com/rasathane/` adresinde emtia bölümü canlı veriyle çalışan, süzülebilir tablolu ve etkileşimli grafikli Rasathane sayfalarının temelini kurmak.

**Architecture:** Python botları rasathane reposunda kalır. Her zamanlanmış koşuda bölümünün sayfa JSON'larını ve grafik serilerini `site-veri/<bolum>/` altına yazıp commit'ler. Sayfalar finfolis Astro'sunda `/rasathane/` altında, ayrı bir şablonla kurulur. finfolis'in `npm run build`'i önce `prebuild` adımında rasathane reposundan yalnız `site-veri/` klasörünü çeker ve `public/rasathane/veri/` altına koyar.

**Tech Stack:** Python 3.12 (pytest, ruff, black, mypy strict); finfolis Astro 7 (`node:test`); lightweight-charts 5; GitHub Actions; finfolis'in mevcut Cloudflare Workers Builds yayını.

**Spec:** `docs/superpowers/specs/2026-11-03-rasathane-site-design.md` (3 Kasım revizyonu: sayfalar finfolis'te)

**Kapsam:** Bu plan ortak altyapıyı ve emtia bölümünü baştan sona kurar. fx, OPsi, INseeder, CAPitAL ve biOF aynı kalıpla sonraki planlarda gelir: her biri bir dışa aktarıcı ve bir iş akışı değişikliği.

**İki repo:**
- rasathane: `C:\DEPO\KOD DEPOSU\para\rasathane` (Task 2–3)
- finfolis: `C:\DEPO\KOD DEPOSU\mecmua\finfolis` (Task 4–6). Başka oturumlar bu klasörde aynı anda commit atıyor: dal değiştirilmez, yalnız bu görevin dosyaları commit'lenir, push'tan önce `git pull --rebase`.

## Global Constraints

- Maliyet sıfır: yeni Worker, D1/KV ya da ücretli plan yok.
- Al/sat dili yasak: "al", "sat", "hedef fiyat", "fırsat", "öneri", "sinyal" sayfa metninde geçmez. Emtia sinyalleri sitede "hareket" ve "uç değer" diye adlandırılır.
- Her sayfanın altında: "Yatırım tavsiyesi değildir. Veriler gecikmelidir." ve sayfanın kaynakları (ad + bağlantı).
- Okura "siz" denir, düğmeler yalın ("Süz", "Sıfırla").
- Kimlik Rasathane'nin kendisi, finfolis'in `Base.astro`'su kullanılmaz: kâğıt `#f6f5f0`, mürekkep `#151515`, ikincil `#6f6b62`, çizgi `#e2dfd6`, vurgu mavi `#2d4fd6` (`ortak/rasathane_ortak/kagit.py`), Inter yazı tipi, işaret `marka/rasathane-isaret.svg`. Stiller `/rasathane/` sayfalarına kapalı kalır, finfolis'in sayfalarına sızmaz.
- Üst şerit: "Bir finfolis yapımıdır" → `https://finfolis.com/`.
- Grafik: her grafik yakınlaştırılabilir, üzerine gelince değer gösterir; eksende büyük sayılar milyon/milyar kısaltmasıyla; 375 px genişlikte okunur.
- Sayı biçimi Türkçe: ondalık virgül, binlik nokta, yüzde `%2,4`; tarihler İstanbul saatiyle.
- TradingView atfı (lightweight-charts lisansı): grafiği olan her sayfada "Grafikler: TradingView Lightweight Charts" bağlantısı (`https://www.tradingview.com/`).
- Repo public: JSON'a sır, Telegram hedefi ya da kişisel veri girmez.
- Var olmayan yol `git add`'e verilmez.
- finfolis `package-lock.json`'ı Windows'ta değişirse diff'te `@emnapi` girdilerinin silinmediği kontrol edilir; push'tan sonra Workers Builds sonucu `gh api repos/senoldak/finfolis/commits/<sha>/check-runs` ile okunur.

## Review Focus

1. **Veri çekilemedi** (GitHub erişilemez, klonlama üç denemede düşer): finfolis derlemesi düşmez, haberler yayımlanır, Rasathane sayfaları "Veri şu an alınamadı" der. → Task 4 testi.
2. **Bölümün hiç verisi yok** (bot henüz koşmamış): bölüm sayfası "Henüz veri yok" der. → Task 5 testi.
3. **Bozuk ya da eski şemalı JSON:** yalnız o sayfa atlanır, derleme uyarıyla sürer. → Task 5 testi.
4. **Eksik değerler** (`None`, NaN): JSON'da `null` olur (asla `NaN` metni değil), tabloda "–" görünür, sıralamada her iki yönde sona düşer. → Task 2 ve Task 5 testleri.
5. **Eski veri ve boş süzme:** `guncellendi` 4 günden eskiyse "(eski)" uyarısı; süzme sıfır satır bırakırsa "Eşleşen satır yok". → Task 5 testleri.

---

### Task 1: Örnek sayfa (onay kapısı)

Sahibin kuralı: görünen değişiklikten önce yerel örnek sayfa. Task 5–6 bu onay gelmeden başlamaz; Task 2–4 paralel sürebilir.

**Files:**
- Create: `C:\DEPO\KOD DEPOSU\mecmua\finfolis\docs\superpowers\ornekler\2026-11-03-rasathane-emtia-pano.html` (tek dosya, gömülü CSS/JS; `docs/superpowers` finfolis'te gitignore'da, commit edilmez)

- [ ] **Step 1:** Emtia panosunun örneğini yaz: üst şerit, Rasathane işareti, bölüm gezintisi (Emtia, Kur, Opsiyon, Yönetici alımları, Kongre işlemleri, Biyoteknoloji takvimi; emtia dışındakiler soluk), başlık ve "Son güncelleme", süzgeç satırı (grup seçimi + metin arama + "Sıfırla"), 20 emtialık tablo (Emtia, Grup, Birim, Kapanış, Günlük, 1 hafta, 1 ay, Yılbaşından beri; başlığa tıklayınca sıralanır), satıra tıklayınca açılan ayrıntı paneli ve lightweight-charts grafiği (cdn.jsdelivr.net'ten sabit sürüm, gerçekçi örnek seri), altta kaynaklar, uyarı ve TradingView atfı. Sayfanın başında "örnek veri" yazar.
- [ ] **Step 2:** Tarayıcıda 1280 px ve 375 px'te aç: sayfa yatay kaymıyor, tablo kendi kutusunda kayıyor.
- [ ] **Step 3:** Ekran görüntülerini sahibine göster, onay ya da düzeltme al. Onaylanan görünüş Task 6'nın ölçütüdür.

### Task 2: Ortak site yazıcısı (rasathane)

**Files:**
- Create: `ortak/rasathane_ortak/site.py`
- Test: `ortak/tests/test_site.py`

**Interfaces:**
- Produces:
  - `SEMA = 1`
  - `@dataclass(frozen=True) class Sutun: anahtar: str; baslik: str; tur: Literal["metin", "sayi", "yuzde", "tarih"]; basamak: int = 2`
  - `@dataclass(frozen=True) class Kaynak: ad: str; url: str`
  - `def sayfa_yaz(kok: Path, bolum: str, sayfa: str, *, baslik: str, aciklama: str, guncellendi: datetime, kaynaklar: Sequence[Kaynak], sutunlar: Sequence[Sutun], satirlar: Sequence[Mapping[str, object]], suzgecler: Sequence[str] = (), grafik: Literal["cizgi", "yok"] = "cizgi") -> Path`: `kok/bolum/sayfa.json` yazar. Satırda sütunlar dışında yalnız `seri` anahtarına (grafik dosyası adı) izin var.
  - `def seri_yaz(kok: Path, bolum: str, anahtar: str, noktalar: Sequence[tuple[date, float]], *, ad: str, birim: str, isaretler: Sequence[tuple[date, str]] = ()) -> Path`: `kok/bolum/seri/<anahtar>.json` yazar.
  - Sayfa JSON: `{"sema":1,"bolum","sayfa","baslik","aciklama","guncellendi":"…Z","kaynaklar":[{"ad","url"}],"sutunlar":[{"anahtar","baslik","tur","basamak"}],"suzgecler":[…],"grafik":"cizgi"|"yok","satirlar":[…]}`
  - Seri JSON: `{"sema":1,"ad","birim","noktalar":[["YYYY-AA-GG",sayı]…],"isaretler":[["YYYY-AA-GG","metin"]…]}`

- [ ] **Step 1: Başarısız testleri yaz**

```python
def test_sayfa_yaz_bicim(tmp_path: Path) -> None:
    yol = sayfa_yaz(tmp_path, "emtia", "pano", baslik="Emtia Panosu", aciklama="a",
        guncellendi=datetime(2026, 11, 3, 23, 30, tzinfo=timezone.utc),
        kaynaklar=[Kaynak("Yahoo Finance", "https://finance.yahoo.com/")],
        sutunlar=[Sutun("ad", "Emtia", "metin"), Sutun("gunluk", "Günlük", "yuzde", 1)],
        satirlar=[{"ad": "Altın", "gunluk": 0.012, "seri": "GC=F"}])
    assert yol == tmp_path / "emtia" / "pano.json"
    d = json.loads(yol.read_text("utf-8"))
    assert d["sema"] == 1 and d["guncellendi"] == "2026-11-03T23:30:00Z"
    assert d["satirlar"][0]["seri"] == "GC=F" and d["grafik"] == "cizgi"

def test_nan_ve_none_null_olur(tmp_path: Path) -> None:
    # satirlar=[{"ad": "X", "gunluk": float("nan")}, {"ad": "Y", "gunluk": None}]
    metin = yol.read_text("utf-8")
    assert "NaN" not in metin
    assert [s["gunluk"] for s in json.loads(metin)["satirlar"]] == [None, None]

def test_sutunda_olmayan_anahtar_reddedilir(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        sayfa_yaz(..., sutunlar=[Sutun("ad", "Emtia", "metin")], satirlar=[{"ad": "X", "fazla": 1}])

def test_gecersiz_bolum_adi(tmp_path: Path) -> None:
    for kotu in ("../x", "Emtia", "a b", ""):
        with pytest.raises(ValueError):
            sayfa_yaz(tmp_path, kotu, "pano", ...)

def test_seri_yaz(tmp_path: Path) -> None:
    yol = seri_yaz(tmp_path, "emtia", "GC=F", [(date(2026, 11, 2), 2701.5), (date(2026, 11, 3), float("nan"))],
        ad="Altın", birim="$/ons", isaretler=[(date(2026, 11, 3), "52 hafta zirvesi")])
    assert yol == tmp_path / "emtia" / "seri" / "GC=F.json"
    d = json.loads(yol.read_text("utf-8"))
    assert d["noktalar"] == [["2026-11-02", 2701.5]]  # NaN nokta atlanır
    assert d["isaretler"] == [["2026-11-03", "52 hafta zirvesi"]]
```

- [ ] **Step 2:** `cd ortak; python -m pytest tests/test_site.py -q` → FAIL (ImportError).
- [ ] **Step 3: Uygula.** `bolum`/`sayfa`: `^[a-z0-9-]{1,40}$`; seri anahtarı: `^[A-Za-z0-9=._^-]{1,40}$`. JSON `ensure_ascii=False, allow_nan=False, sort_keys=True`; önce `.tmp`'ye yazılır, `os.replace` ile taşınır. float NaN/inf → `None`. Yeni bağımlılık yok.
- [ ] **Step 4:** `python -m pytest -q` → PASS.
- [ ] **Step 5:** `git add ortak/rasathane_ortak/site.py ortak/tests/test_site.py; git commit -m "Ortak: site JSON yazıcısı"`

### Task 3: Emtia dışa aktarıcısı ve iş akışı (rasathane)

**Files:**
- Create: `emtia/rasathane_emtia/site_aktar.py`
- Modify: `emtia/rasathane_emtia/raporlar.py` (`Stok` ve `Pozisyon`'a `gecmis`)
- Modify: `emtia/rasathane_emtia/calistir.py` (`site_dizini: Path | None = None` parametresi)
- Modify: `emtia/rasathane_emtia/__main__.py` (`--site DIZIN`)
- Modify: `.github/workflows/emtia.yml`
- Test: `emtia/tests/test_site_aktar.py`, `emtia/tests/test_emtia.py`

**Interfaces:**
- Consumes: Task 2'den `sayfa_yaz`, `seri_yaz`, `Sutun`, `Kaynak`.
- Produces:
  - `raporlar.Stok.gecmis: tuple[tuple[str, float], ...] = ()` (`eia_stok`'un zaten çektiği 60 hafta, en yeni önce); `raporlar.Pozisyon.gecmis: tuple[tuple[str, int], ...] = ()` (`cot`'un zaten çektiği haftalar). Ek istek yok.
  - `def aktar(kok: Path, simdi: datetime, tarih: str, bugunku: dict[str, pd.DataFrame], olcumler: dict[str, Olcum], gram: pd.Series | None, gram_olcum: Olcum | None, oran_olcumleri: list[OranOlcum], hareketler: list[Sinyal], rapor: dict[str, Any]) -> list[Path]`: `kok / "emtia"` altına yazar.
  - Sayfalar: `pano` (20 emtia + gram altın + USD/TRY + dolar endeksi; süzgeç `grup`), `oranlar` (4 oran, 5 yıllık yüzdelik), `hareketler` (günün bütün sert hareket ve 52 hafta zirve/dip satırları, susturma uygulanmaz; süzgeç `tur`), `stoklar` (EIA, rapor varsa), `fonlar` (CFTC, rapor varsa).
  - Seriler: her emtia ve gram için son 252 işlem günü kapanış; her oran için son 252 gün; EIA ve CFTC için `gecmis`. Anahtarlar: sembol (`GC=F`), `gram`, `oran-<anahtar>`, `eia-<seri>`, `cftc-<sembol>`. Hareket satırlarının serisinde hareket günü `isaretler`'e yazılır.
  - Kaynaklar: Yahoo Finance (pano, oranlar, hareketler), EIA (`https://www.eia.gov/`), CFTC (`https://www.cftc.gov/`).

- [ ] **Step 1: Başarısız testleri yaz** (mevcut `_df`/`_yuruyus` yardımcılarıyla)
  - `test_aktar_sayfa_ve_seriler`: 22 sembollük sahte `bugunku` → `pano.json`, `oranlar.json`, `hareketler.json` var; `pano` 23 satır; `seri/GC=F.json` 252 nokta.
  - `test_rapor_yoksa_stok_ve_fon_yazilmaz`: `rapor={}` → `stoklar.json`/`fonlar.json` yazılmaz, önceden var olanlar silinmez.
  - `test_hareket_isaretli`: son günü %8 sıçrayan seri → `hareketler.json`'da satır, serisinde o günün işareti.
  - `test_metinde_yasak_sozcuk_yok`: yazılan bütün JSON metinlerinde `\b(al|sat|sinyal|öneri|fırsat)\b` (büyük/küçük harf duyarsız) yok.
  - `test_calistir_kuru_site_yazar` (`test_emtia.py`): `calistir(kuru=True, site_dizini=tmp/"sv", indir=sahte, rapor_kaynagi=lambda: {})` → `tmp/sv/emtia/pano.json` var; `site_dizini=None` iken site dosyası yok.
  - `test_eia_cot_gecmis`: sahte `al` ile `eia_stok` ve `cot` → `gecmis` uzunlukları 60 ve 157, en yeni önce.
- [ ] **Step 2:** `cd emtia; python -m pytest -q` → yeni testler FAIL.
- [ ] **Step 3: Uygula.** `calistir` içinde `rapor = rapor_kaynagi()` satırından hemen sonra, kart çiziminden ve kuru dönüşünden önce: `if site_dizini: site_aktar.aktar(site_dizini, simdi, tarih, bugunku, olcumler, gram, gram_olcum, oran_olcumleri, bulunan, rapor)`. Çağrı `try/except` içinde; hata `log.warning` ile yazılır, Telegram akışını durdurmaz. `--site` yoksa davranış bugünküyle aynı.
- [ ] **Step 4:** `python -m pytest -q; python -m ruff check rasathane_emtia tests; python -m black --check rasathane_emtia tests; python -m mypy rasathane_emtia` → temiz.
- [ ] **Step 5: İş akışı.** "Kartları üret ve gönder" adımına `SITE: ${{ inputs.kuru == true && '0' || '1' }}`; `SITE=1` iken `ARGS+=(--site ../site-veri)`. "Kaydı depoya yaz" adımında `[ -d veri ] || exit 0` yerine `for y in veri ../site-veri/emtia; do [ -e "$y" ] && git add "$y"; done`, ardından mevcut boş diff kontrolü. Commit mesajı `Emtia: kayıt ve site verisi $(date -u +%F)`.
- [ ] **Step 6:** README'nin Zamanlanmış işler bölümüne bir satır: botlar `site-veri/`'yi yazar, finfolis bunu `/rasathane/` için okur. Commit: `git commit -m "Emtia: site verisi dışa aktarımı"`; push.
- [ ] **Step 7:** Actions → Emtia → "Run workflow" (`kuru` işaretsiz, sahibin onayıyla; gerçek Telegram gönderimi `EMTIA_GONDER` değişkenine bağlı kalır) ya da ilk zamanlanmış koşuyu bekle → repoda `site-veri/emtia/pano.json` var.

### Task 4: finfolis'te veri çekme (prebuild)

**Files (finfolis):**
- Create: `scripts/rasathane/veri-cek.mjs`, `scripts/rasathane/veri-cek.test.mjs`
- Modify: `package.json` (`"prebuild": "node scripts/rasathane/veri-cek.mjs"`)
- Modify: `.gitignore` (`public/rasathane/veri/`, `.rasathane-veri/`)

**Interfaces:**
- Produces: `export async function veriCek({ hedef, depo = 'https://github.com/senoldak/rasathane.git', gecici = '.rasathane-veri', komut = calistirGit, deneme = 3, yerel = process.env.RASATHANE_VERI_DIZINI }): Promise<{ durum: 'tamam' | 'alinamadi', dosya: number }>`
  - `yerel` verilirse klonlama yerine o klasörden kopyalar (yerel geliştirme ve testler).
  - Başarıda `hedef` temizlenir, `site-veri/**` altındaki yalnız `^[a-z0-9-]+/(seri/)?[A-Za-z0-9=._^-]+\.json$` yollar kopyalanır; `hedef/_durum.json` = `{"durum":"tamam","cekildi":ISO}`.
  - Üç denemede de başarısızsa `hedef/_durum.json` = `{"durum":"alinamadi"}`, süreç 0 koduyla biter.
  - Klonlama: `git clone --depth 1 --filter=blob:none --sparse <depo> <gecici>` + `git -C <gecici> sparse-checkout set site-veri`.

- [ ] **Step 1: Başarısız testleri yaz** (`komut` sahte, `yerel` geçici klasör)
  - Başarılı kopya: `emtia/pano.json` ve `emtia/seri/GC=F.json` kopyalanır; `emtia/notlar.txt` ve `../kacak.json` kopyalanmaz; `_durum.json` `tamam`.
  - Hedefteki eski dosya (`emtia/eski.json`) yeni çekimde silinir.
  - `komut` her seferinde hata fırlatır → 3 deneme, `durum: 'alinamadi'`, `_durum.json` yazılı, istisna dışarı sızmaz.
- [ ] **Step 2:** `node --test scripts/rasathane/` → FAIL.
- [ ] **Step 3: Uygula.** Yeni bağımlılık yok (`node:child_process`, `node:fs`).
- [ ] **Step 4:** `node --test scripts/rasathane/` → PASS; `npm test` → eski testler de PASS.
- [ ] **Step 5:** Yerelde `node scripts/rasathane/veri-cek.mjs` gerçek repodan çeker (Task 3 Step 7'den sonra `public/rasathane/veri/emtia/pano.json` var; öncesinde `_durum.json` `tamam` ve klasör boş).
- [ ] **Step 6:** Commit (yalnız bu dosyalar): `git commit -m "Rasathane: derlemede site verisini çek"`. Push Task 6 ile birlikte yapılır.

### Task 5: finfolis'te Rasathane kütüphanesi (saf işlevler)

**Files (finfolis):**
- Create: `src/lib/rasathane/veri.mjs`, `src/lib/rasathane/veri.test.mjs`
- Create: `src/lib/rasathane/bicim.mjs`, `src/lib/rasathane/bicim.test.mjs`
- Create: `src/lib/rasathane/tablo.mjs`, `src/lib/rasathane/tablo.test.mjs`
- Create: `src/lib/rasathane/bolumler.mjs`

**Interfaces:**
- Consumes: Task 2'nin JSON biçimi; Task 4'ün `_durum.json`'u.
- Produces:
  - `BOLUMLER = [{anahtar:"emtia",ad:"Emtia"},{anahtar:"fx",ad:"Kur"},{anahtar:"opsi",ad:"Opsiyon"},{anahtar:"inseeder",ad:"Yönetici alımları"},{anahtar:"capital",ad:"Kongre işlemleri"},{anahtar:"biof",ad:"Biyoteknoloji takvimi"}]`
  - `veriDurumu(kok): 'tamam' | 'alinamadi'` (`_durum.json` yoksa `'alinamadi'`)
  - `sayfalariOku(kok, simdi = new Date()): {bolum, sayfa, veri, eski}[]`: `kok/<bolum>/<sayfa>.json` (`seri/` hariç); `sema !== 1` ya da zorunlu alan eksikse `console.warn` ile atlar; `eski` = `guncellendi` 4 günden eski.
  - `sayi(x, basamak = 2)`, `yuzde(x, basamak = 1)`, `tarih(iso)`: `null`/`undefined` → `"–"`.
  - `sirala(satirlar, anahtar, yon: "artan"|"azalan")`: `null` her iki yönde sonda; metin `localeCompare(…, "tr")`.
  - `suz(satirlar, {metin?, secimler?}, metinSutunlari)`: metin `toLocaleLowerCase("tr")` ile aranır; seçimler tam eşleşme.

- [ ] **Step 1: Başarısız testleri yaz**
  - `veri.test.mjs`: geçerli + `sema: 2` + bozuk JSON → yalnız geçerlisi; klasör yok → `[]`; `guncellendi` 5 gün önce → `eski: true`, 1 gün önce → `false`; `seri/` altı sayfa sayılmaz; `_durum.json` `alinamadi` → `veriDurumu` `'alinamadi'`.
  - `bicim.test.mjs`: `yuzde(0.0243, 2) === "%2,43"`, `yuzde(-0.1) === "-%10,0"`, `sayi(1234567.891) === "1.234.567,89"`, `sayi(null) === "–"`, `tarih("2026-11-03T23:30:00Z") === "4 Kasım 2026"`.
  - `tablo.test.mjs`: `[3, null, 1]` artan `[1, 3, null]`, azalan `[3, 1, null]`; `["Şeker","Altın","İnek"]` artan `["Altın","İnek","Şeker"]`; `suz({metin:"ALTIN"})` "Altın" ve "Gram altın"ı bulur; `suz({metin:"ı"})` "Altın"ı bulur; eşleşme yoksa `[]`.
- [ ] **Step 2:** `npm run test:site` → yeni testler FAIL.
- [ ] **Step 3: Uygula** dört dosyayı. Yeni bağımlılık yok.
- [ ] **Step 4:** `npm run test:site` → PASS.
- [ ] **Step 5:** Commit: `git commit -m "Rasathane: veri okuma, biçim ve tablo işlevleri"`

### Task 6: finfolis'te Rasathane sayfaları, tablo ve grafik

**Files (finfolis):**
- Create: `src/layouts/RasathaneKabuk.astro`
- Create: `src/pages/rasathane/index.astro`, `src/pages/rasathane/[bolum]/index.astro`, `src/pages/rasathane/[bolum]/[sayfa].astro`
- Create: `src/components/rasathane/Tablo.astro`, `src/components/rasathane/Grafik.astro`
- Create: `public/rasathane/isaret.svg` (`marka/rasathane-isaret.svg` kopyası), `public/rasathane/fontlar/` (Inter woff2 + lisans)
- Modify: `package.json`, `package-lock.json` (`lightweight-charts` `^5`)

**Interfaces:**
- Consumes: Task 5'in bütün işlevleri; seri dosyaları `/rasathane/veri/<bolum>/seri/<anahtar>.json`.

- [ ] **Step 1: Şablon.** `RasathaneKabuk.astro`: kendi `<html>`'i, kendi stili (yalnız bu şablonda), üst şerit, işaret + "Rasathane", bölüm gezintisi (verisi olmayan bölüm soluk ama tıklanabilir), içerik, alt bilgi (uyarı, `https://finfolis.com/hakkimizda/` (künye orada)). Görünüş Task 1'de onaylanan örneğe uyar.
- [ ] **Step 2: Sayfalar.** Ana sayfa: bölümler ve sayfaları, her birinin son güncellemesi; `veriDurumu` `alinamadi` ise üstte "Veri şu an alınamadı". `[bolum]/index`: `getStaticPaths` bütün `BOLUMLER`'i üretir; verisi yoksa "Henüz veri yok". `[bolum]/[sayfa]`: başlık, açıklama, son güncelleme (eskiyse "(eski)"), tablo, kaynaklar, atıf.
- [ ] **Step 3: Tablo.** Tablo sunucuda tam çizilir (JS olmadan okunur). Betik başlık tıklamasıyla `sirala`, `suzgecler` için `<select>` + metin kutusu + "Sıfırla" ile `suz` kullanır; sonuç boşsa "Eşleşen satır yok". Tablo `overflow-x: auto` kutuda, ilk sütun sabit.
- [ ] **Step 4: Grafik.** Satır tıklaması ve Enter tuşu ayrıntı panelini açar. `seri` varsa dosyayı `fetch` eder, lightweight-charts çizgi grafiği çizer (Türkçe sayı biçimi, `isaretler` grafik işareti); yükleme başarısızsa "Grafik yüklenemedi". `grafik: "yok"` ya da satırda `seri` yoksa panel yalnız satır ayrıntısını gösterir.
- [ ] **Step 5: Derleme.** `RASATHANE_VERI_DIZINI` ile Task 3 testlerinin ürettiği örnek veriyi göstererek `npm run build` → `dist/rasathane/index.html`, `dist/rasathane/emtia/pano/index.html`, `dist/rasathane/fx/index.html` ("Henüz veri yok") var; finfolis'in mevcut derleme denetimleri (etkileşimli grafik denetimi dahil) geçer. Örnek veri `public/rasathane/veri/` altında kalır, gitignore'da.
- [ ] **Step 6: Tarayıcı denemesi.** `npm run preview` ile `/rasathane/emtia/pano/`: sıralama, süzme, "Sıfırla", satır grafiği, yakınlaştırma ve üzerine gelince değer; 375 px'te sayfa yatay kaymıyor; finfolis ana sayfası ve bir haber sayfası eskisi gibi görünüyor. Ekran görüntüsü al.
- [ ] **Step 7:** `package-lock.json` diff'inde `@emnapi` silinmesi yok. `npm test` → PASS.
- [ ] **Step 8:** Commit (yalnız bu görevin dosyaları): `git commit -m "Rasathane: /rasathane/ sayfaları, tablo ve grafik"`; `git pull --rebase`; Task 4 ile birlikte push.
- [ ] **Step 9: Canlı doğrulama.** Workers Builds sonucu başarılı (`gh api repos/senoldak/finfolis/commits/<sha>/check-runs`). `https://finfolis.com/rasathane/` ve `https://finfolis.com/rasathane/emtia/pano/` 200; `/rasathane/veri/emtia/seri/GC=F.json` 200; finfolis ana sayfası ve bir haber sayfası 200. Emtia'nın bir sonraki koşusundan ve finfolis'in bir sonraki derlemesinden sonra "Son güncelleme"nin ilerlediğini doğrula.
