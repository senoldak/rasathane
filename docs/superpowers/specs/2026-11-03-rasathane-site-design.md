# Rasathane sitesi: finfolis.com/rasathane — tasarım

> 3 Kasım revizyonu (sahibin önerisi): sayfalar finfolis Astro'sunda, botlar rasathane'de; ayrı Worker kaldırıldı.

Tarih: 3 Kasım 2026. Durum: taslak, sahibin onayını bekliyor.

## Amaç ve neden

Rasathane botları her gün hazır piyasa taramaları üretiyor ama bunlar yalnız Telegram kartı olarak (`t.me/rasathane`) yaşıyor. Kart bir resim: süzülmez, sıralanmaz, geçmişi gezilmez. Site bu taramaları web'de, kendi başına okunan, TradingView havasında süzülüp sıralanabilen sayfalar hâline getirir.

Okur hisseler arasında boğulmak istemez. Site bir evren tarayıcısı değildir; botların zaten seçtiği küçük listeleri gösterir. Her tarama bir sayfadır; okur o listeyi süzer, sıralar, bir satıra tıklayıp grafiğini açar.

## Hedefler

- `finfolis.com/rasathane/` adresinde, Rasathane'nin bütün hazır taramalarını gösteren site.
- Her tarama sayfası: süzülebilir/sıralanabilir tablo + satıra tıklayınca açılan etkileşimli grafik.
- Veri her botun koşusundan sonra rasathane reposuna yazılır; site finfolis'in bir sonraki derlemesinde (bugün yaklaşık iki saatte bir) tazelenir. Gecikmeli veridir ve sayfada öyle yazar.
- Maliyet sıfır: iki public repo Actions + finfolis'in mevcut Workers Builds derlemeleri; yeni Worker, servis ya da kota yok.
- Telefonda okunur.

## Hedef dışı

- Canlı / saniyelik fiyat. Gerçek zamanlı akış yok.
- Kullanıcının kendi tarama kurduğu, bütün piyasayı süzdüğü genel bir screener.
- Hesap, giriş, izleme listesi, bildirim.
- finfolis'in haberlerine, tasarımına ya da mevcut sayfalarına dokunmak. Rasathane sayfaları finfolis Astro'sunda ayrı bir şablon ve `/rasathane/` altında ayrı klasörlerle yaşar.

## Kaçınılacaklar (çalışsa da başarısızlık sayılır)

- Al/sat dili: "al", "sat", "hedef fiyat", "fırsat", "öneri" gibi sözcükler. Sayfalar veriyi ve geçmiş isabeti gösterir, yön söylemez. Her sayfanın altında "yatırım tavsiyesi değildir" notu.
- Etkileşimsiz grafik (finfolis kuralı): grafik yakınlaştırılabilir, üzerine gelince değer gösterir.
- Telefonda taşan tablo, okunmayan eksen; eksende büyük sayılar milyar/milyon kısaltmasıyla.
- Bir botun hatasının siteyi ya da öteki botları düşürmesi.
- Ücret doğuran herhangi bir kaynak (ücretli plan, D1/KV kotası, sunucu).

## Kapsam: hangi taramalar

Sahibin kararı: hepsi girer.

| Bölüm | Sayfalar (botun kartlarıyla aynı) |
|---|---|
| emtia | pano, sert hareketler, 52 hafta zirve/dip, EIA stokları, CFTC fon pozisyonları, gram altın |
| fx | pano, risk iştahı, carry, faiz farkları, Fed beklentisi, kur bağları, oynaklık, seanslar, CFTC, sinyal karnesi, kura duyarlı hisseler |
| OPsi | opsiyon taraması, oynaklık (ETF dahil) |
| INseeder | yönetici açık piyasa alımları (Form 4) |
| CAPitAL | Kongre üyelerinin işlem beyanları |
| biOF | biyoteknoloji takvimi: FDA tarihleri, faz sonuçları |

bist henüz yayında değil; şimdilik ona site bağlantısı kurulmaz, hazır olunca aynı yolla eklenir. OPsi, INseeder, CAPitAL ve biOF için sitede Türkçe bölüm adları kurucunun önerisiyle konur (ör. Opsiyon, Yönetici alımları, Kongre işlemleri, Biyoteknoloji takvimi).

Sinyal karnesi: "sinyal" sözcüğü sitede geçmez; sayfa yalnız geçmiş isabet oranını ve kayıtları gösterir.

## Kısıtlar ve sahibin kararları

- **Veri kaynağı:** Yahoo Finance dahil botların bugün kullandığı kaynaklar aynen kullanılır; veri gecikmeli verilir. Yahoo şartlarıyla ilgili risk konuşuldu, sahip kabul etti.
- **Hukuki çerçeve:** Sahip al/sat dili olmadığı için hukuki risk görmüyor; yukarıdaki dil kuralları bunun şartıdır.
- **Kimlik:** Rasathane'nin kendi kimliği — `marka/` işareti, kartlardaki kâğıt zemin ve yazı dili. En üstte ince bir şerit: "bir finfolis yapımıdır" → finfolis.com. Altta finfolis künyesiyle aynı künye. finfolis'in renkleri/bileşenleri kopyalanmaz; yalnız grafik kuralları ortak.
- **Okura hitap:** "siz", düğmeler yalın (finfolis/kifobu kuralı).
- **Önce örnek sayfa:** Koda geçmeden yerelde bir örnek sayfa (emtia panosu: filtre + tablo + grafik) gösterilir; kimlik ve düzen onun üstünde onaylanır.
- **Repo public:** Sır, anahtar, Telegram hedefi siteye ya da JSON'a girmez.

## Yaklaşımlar

1. rasathane reposunda ayrı statik site + ayrı Worker, finfolis'ten servis bağlantısıyla — önce seçildi, sonra sahibin önerisiyle bırakıldı: ayrı Worker, token ve elle yayın adımları gereksiz yük.
2. **Botlar rasathane'de, sayfalar finfolis'te — SEÇİLDİ (sahibin önerisi, 3 Kasım).** Python botları rasathane reposunda kalır ve `site-veri/<bolum>/` altına JSON yazar. `/rasathane/` sayfaları finfolis Astro'sunda kurulur; finfolis her derlemede (`prebuild`) rasathane reposundan yalnız `site-veri/` klasörünü çeker. Botları da finfolis'e taşımak reddedildi: bot commit'leri haber botuyla çakışır, biOF'un saatlik commit'leri finfolis'i her saat derletip Workers Builds dakikasını yer.
3. Worker + D1 dinamik site — reddedildi: günde bir değişen veri için gereksiz karmaşıklık ve geçmişte aşılmış kotalar.

## Mimari (kararlaştırılan kısım)

- **Veri dışa aktarımı:** Her bot, kart çizdiği aynı sonuçtan rasathane reposunda `site-veri/<bolum>/<sayfa>.json` ve grafik serileri için `site-veri/<bolum>/seri/<anahtar>.json` üretir. Ortak yazıcı `ortak/` paketine girer (`rasathane_ortak.site`), şema her bölüm için aynı iskelette.
- **Kuru koşu ve site yazımı (tasarımcının kararı):** Site verisi Telegram gönderiminden bağımsızdır: zamanlanmış (ya da vesaire'nin tetiklediği) her koşu, Telegram gönderimi kapalı olsa bile `site-veri`'yi yazar. Elle başlatılan kuru koşu siteye yazmaz; JSON'u yalnız yapıt olarak yükler. Ayrım tek bir ortam değişkeniyle yapılır (`SITE_YAZ=1`), deneme koşusu canlı veriyi ezemez.
- **Commit:** Mevcut "Kaydı depoya yaz" adımına `site-veri/<bolum>` eklenir. Yol yoksa `git add` koşulsuz çağrılmaz (geçmişte commit'i düşüren tuzak). Her bot yalnız kendi bölüm klasörüne yazar; çakışma olmaz, mevcut `pull --rebase` döngüsü yeter.
- **Yayın:** Ayrı yayın işi yok. finfolis'in `npm run build`'i önce `prebuild` adımında rasathane reposunu yalnız `site-veri/` için sığ ve seyrek klonlar (`git clone --depth 1 --filter=blob:none --sparse` + `sparse-checkout set site-veri`), dosyaları `public/rasathane/veri/`'ye koyar. finfolis zaten haber botu commit'leriyle yaklaşık iki saatte bir derleniyor; rasathane verisi bu derlemelerle tazelenir.
- **Adres:** `finfolis.com/rasathane/` finfolis'in kendi statik sayfalarıdır; Worker, servis bağlantısı, DNS ya da token değişikliği yok, sahibin elle adımı yok.
- **Grafikler sayfa türüne göre (tasarımcının kararı):** Her satır bir ayrıntı paneli açar. Grafik, satırın gerçek bir zaman serisi olduğu yerde çizilir:
  - Fiyatlı satırlar (emtia panosu, sert hareketler, 52 hafta, fx panosu, kura duyarlı hisseler, OPsi'de dayanak varlık): son 1 yıl günlük kapanış.
  - EIA stokları: stok serisi; CFTC: net pozisyon geçmişi; faiz farkları/carry/Fed beklentisi: ilgili faiz serileri; sinyal karnesi: zaman içinde isabet oranı.
  - Olay/beyan sayfaları (INseeder, CAPitAL, biOF): ayrıntı paneli kaynak belgeye bağlantı, işlem ayrıntısı ve şirketin hisse grafiği (işlem/olay tarihi grafikte işaretli). Hisse yoksa grafik çizilmez.
  - Seanslar gibi seri taşımayan sayfalarda grafik yoktur; "etkileşimsiz grafik yok" kuralı çizilen her grafik için geçerlidir.
- **Geçmiş verinin kaynağı:** Bot, kartı çizerken zaten indirdiği geçmişi kullanır. Yetmiyorsa geçmişi yine kendi koşusunda çeker, site işi veri çekmez. Bir botun çekimi düşerse yalnız o bölüm eski kalır.
- **Kaynaklar ve haklar:** Yahoo için alınan karar, Yahoo üstünden gelen Borsa İstanbul fiyatlarını da kapsar. Gecikmeli verilir ve kaynak adı yazılır. FRED, ECB, BIS, EIA, CFTC, SEC ve Kongre beyanları kamu verisidir. Her sayfa kaynaklarını adıyla ve bağlantısıyla gösterir.
- **Ön yüz:** Astro statik sayfalar; tablo süzme/sıralama küçük bir istemci betiğiyle (ağır tablo kütüphanesi şart değil). Grafik: TradingView **lightweight-charts** (Apache 2.0); lisansın istediği TradingView atıf bağlantısı sayfada görünür.
- **Hata yalıtımı:** Bir botun koşusu düşerse o bölüm repodaki son iyi JSON'la kalır ve "son güncelleme" bunu gösterir. Klonlama düşerse (üç deneme) finfolis derlemesi düşmez; Rasathane sayfaları "Veri şu an alınamadı" der, haberler etkilenmez. Bozuk JSON yalnız o sayfayı atlatır.

## Kurucuya bırakılanlar

- Botların sonuçlarının yapısı: kurucu planlamadan önce her botun (özellikle INseeder SQLite, CAPitAL, OPsi) kartı hangi yapıdan çizdiğine bakar; resimden geriye veri çıkarılmaz, kartı besleyen satırlar dışa aktarılır.
- JSON boyut sınırı ve "son güncelleme" uyarısının eşiği.
- JSON şemasının alan adları ve bölüm başına sütunlar (kartlardaki sütunlarla başlanır).
- Grafik geçmişinin uzunluğu ve dosya bölümü (sayfa boyutu makul kaldığı sürece).
- Astro sayfa düzeni, gezinme, ana sayfanın içeriği (bölümlere giriş + son güncellemeler önerilir).
- Testler: her botun JSON yazıcısı için birim testi; şema doğrulaması derlemede.

## graFİX bölümü (sahibin kararı, 3 Kasım)

- **Kod gizli kalır:** graFİX kodu `senoldak/rasathane-ic` içinde (`graFIX/grafix/`) kalır. Açık depoya kod konmaz.
- **Sonuçlar açık:** graFİX her koşusunun sonunda site verisini (`site-veri/grafix/`) açık `senoldak/rasathane` deposuna yazar. Site bu veriyi mevcut prebuild çekimiyle alır; finfolis'e yeni sır gerekmez.
- **Sayfalar:** `/rasathane/grafix/` bugünkü formasyonların süzülebilir tablosu (sembol, tür, tarih, kapanış); `/rasathane/grafix/<sembol>/` fiyat grafiği, son 1 yıl, seçilebilir göstergeler (EMA 233/377, SMA 200, Kijun) ve o hisseye ait sinyal geçmişi.
- **Dil:** "sinyal" sözcüğü yok; "formasyon" ya da "kesişim" kullanılır. Al/sat dili yok (graFİX README'si zaten bunu söylüyor).
- **Veri kaynağı:** Yahoo günlük kapanış; emtia için verilen karar burada da geçerli (gecikmeli, kaynak adıyla).
- **Yazma yetkisi:** graFİX iş akışı açık depoya yazmak için bir token kullanır. Hangi token ve kapsamı, sahibin onayıyla belirlenir; kapsam yalnız `senoldak/rasathane` içindeki `site-veri/grafix/` ile sınırlı olmalı.
- **Açık sorular (plan aşamasında):** ~500 sembol sayfası için sitemap ve JSON boyutu; GOOG/GOOGL gibi çift sınıflar için tek sayfa mı iki sayfa mı.
