# Ürün Bağlamı

Bu belge PDFtoEPUB'nin kullanıcı problemini, hedef kullanıcılarını ve gözlemlenebilir ürün davranışını tanımlar. Teknik ayrıntılar `docs/tech-context.md` ve `docs/architecture.md` içinde tutulur.

## Ürün Amacı

- Ürün adı: `PDFtoEPUB`
- Çözdüğü problem: Sabit sayfa düzenine sahip yerel PDF'leri elektronik kitap okuyucularında rahatça okunabilen yeniden akışlı EPUB dosyalarına dönüştürme ihtiyacı.
- Temel değer önerisi: Kullanıcı, çevrim içi bir dönüştürme servisine PDF yüklemeden, metin düzenini ve temel kitap yapısını mümkün olduğunca koruyan bir EPUB elde eder.

## Hedef Kullanıcılar

- Birincil kullanıcı: Windows üzerinde yerel PDF kitap veya dokümanlarını EPUB olarak okumak isteyen kullanıcı.
- İkincil kullanıcı: Dönüşüm seçeneklerini komut satırından veya `PdfToEpubConverter` servisi üzerinden kullanan geliştirici ve otomasyon kullanıcısı.
- Kullanıcı hedefi: PDF seçmek, dönüşümü beklemek ve doğrulanabilir bir `.epub` çıktısını okuyucuya aktarmak.
- Kullanıcı kısıtları: Girdi dosyası yerel olmalıdır; OCR gereken belgelerde Tesseract ve Türkçe model gerekir; GUI kullanımı Windows odaklıdır; PDF'nin görsel düzeni birebir korunmaz.

## Temel Kullanım Senaryoları

1. Kullanıcı GUI'yi açar, yerel bir `.pdf` dosyasını bırakır ve dönüşüm otomatik başlar; çıktı İndirilenler klasörüne `<başlık>-EPUB.epub` adıyla yazılır.
2. Kullanıcı CLI'ye bir PDF yolu verir, çıktı yolunu ve dönüşüm seçeneklerini belirler; işlem sonunda EPUB ve dönüşüm özeti alır.
3. Kullanıcı taranmış veya metinsiz bir PDF verdiğinde, Tesseract ve `tur.traineddata` kullanılabiliyorsa OCR metni sayfa geometrisiyle birlikte işlenir.
4. Şifreli PDF için CLI kullanıcısı `--password` sağlar; parola eksik veya hatalıysa uygulama anlaşılır bir dönüşüm hatası bildirir.
5. Kullanıcı dönüşümü GUI'den iptal eder; uygulama sayfa sınırında iptali kontrol eder ve iptal durumunu bildirir.

## Ürün Hedefleri

- Geçerli bir PDF'den EPUB 3 yapısına uygun, yeniden akışlı ve dahili olarak doğrulanmış bir çıktı üretmek.
- Başlıkları, bölümleri, paragrafları, listeleri, temel tabloları, dipnotları ve seçili görselleri anlamsal öğeler olarak korumaya çalışmak.
- PDF metin katmanı yetersiz olduğunda yerel OCR ile kurtarma yolu sağlamak; PDF içeriğini uzak bir servise göndermemek.
- CLI ve GUI'nin aynı dönüşüm servisini kullanmasını sağlayarak davranış farkını azaltmak.
- Başarısızlıkları sessizce yok saymak yerine kullanıcıya hata, uyarı ve log bilgisi sunmak.

## Kapsam Dışı

- PDF'nin görsel görünümünü piksel düzeyinde yeniden üretmek.
- Uzak dönüştürme servisi, kullanıcı hesabı, bulut depolama veya veritabanı sağlamak.
- PDF bağlantılarını, vektör çizimlerini, formları, açıklamaları ve tüm gelişmiş PDF etkileşimlerini EPUB'a taşımak.
- Geometrik veya karmaşık tabloları genel amaçlı olarak yeniden kurmak.
- GUI üzerinden parola, çıktı yolu veya gelişmiş OCR dili seçimi sunmak.
- OCR dillerini kullanıcı arayüzünden yapılandırmak. Mevcut davranışta dil `tur` olarak belirlenmiştir.

## Kullanıcı Deneyimi ve İş Kuralları

- GUI, dosya seçme adımlarını azaltmak için yalnızca yerel PDF sürükle-bırak akışı kullanır ve bırakma sonrasında dönüşümü otomatik başlatır.
- Varsayılan dönüşümde tekrarlanan üstbilgi/altbilgi ve kenar sayfa numaraları kaldırılır; satır içi görseller kapalıdır; ilk sayfa kapak olarak algılanırsa korunur.
- CLI'de çıktı yolu verilmezse girdi dosyasının uzantısı `.epub` olacak şekilde aynı temel ad kullanılır.
- Çıktı yolu `.epub` ile bitmiyorsa uzantı `.epub` yapılır; mevcut hedef dosya onay sorulmadan atomik olarak değiştirilebilir.
- Girdi PDF'si okunur, ancak dönüştürme sırasında değiştirilmez.
- OCR veya PDF açma gibi zorunlu bir adım başarısızsa işlem ya anlaşılır bir hata ile durur ya da güvenli şekilde ilgili sayfayı atlar; güvenilmez gizli metin sessizce doğru kabul edilmez.
- GUI dönüşüm işi ana arayüz iş parçacığını bloklamaz; iptal isteği işlenen sayfanın tamamlanmasının ardından uygulanabilir.

## Başarı Ölçütleri

- Geçerli bir PDF için komut satırı dönüşümü sıfır çıkış kodu ile tamamlanır ve hedef `.epub` dosyası oluşur.
- Oluşturulan EPUB'da `mimetype`, `META-INF/container.xml`, OPF manifest/spine, navigasyon ve XHTML referansları dahili doğrulamadan geçer.
- Metin içeren sentetik PDF testleri başlık, bölüm, paragraf, üstbilgi/altbilgi, sayfa numarası, görsel ve EPUB paket davranışını doğrular.
- GUI smoke testi uygulamanın arayüzü başlatıp hemen kapanabildiğini doğrular.
- Dönüşüm özeti işlenen sayfa, algılanan yapı öğeleri, OCR sayfaları ve uyarı sayısını raporlar.

## Bağlam Güncelleme Kuralları

- Ürün amacı, hedef kullanıcı veya kapsam değişirse bu dosya güncellenir.
- Geçici fikirler `PROGRESS.md` veya `TODO.md` içine yazılır; doğrulanan kapsam bilgisi buraya taşınır.
- Uygulama komutları ve bağımlılıklar `docs/tech-context.md` içinde, bileşen ilişkileri `docs/architecture.md` içinde tutulur.
