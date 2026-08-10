# Mimari Genel Bakış

Bu belge PDFtoEPUB'nin bileşenlerini, veri akışını ve değişmemesi gereken sınırlarını açıklar.

## Sistem Özeti

Uygulama CLI, GUI veya doğrudan `PdfToEpubConverter.convert()` çağrısıyla bir PDF yolu alır. `ConversionPipeline`, PyMuPDF ile sayfa metnini ve seçili görselleri çıkarır; gerekli olduğunda yerel Tesseract OCR kullanır ve koordinatlı blokları başlık, paragraf, bölüm, liste, tablo, dipnot ve görsel gibi anlamsal öğelere dönüştürür. Bu format bağımsız `SemanticDocument`, `EpubBuilder` tarafından EPUB 3 arşivine yazılır; çıktı yayınlanmadan önce dahili validator ile kontrol edilir. GUI, aynı servis çağrısını `QThread` tabanlı worker içinde çalıştırarak arayüzü serbest tutar.

## Bileşenler

| Bileşen | Sorumluluk | Konum |
| --- | --- | --- |
| Giriş yönlendirici | Argümana göre GUI veya CLI başlatır. | `uygulama/run.py` |
| CLI | Argümanları parse eder, seçenekleri oluşturur, ilerleme ve sonucu konsola yazar. | `uygulama/app/cli.py` |
| GUI bootstrap | QApplication, stil, ikon ve smoke-test yaşam döngüsünü kurar. | `uygulama/app/main.py` |
| GUI ana penceresi | PDF sürükle-bırak, ilerleme, log, iptal ve çıktı açma işlemlerini yönetir. | `uygulama/app/gui/main_window.py` |
| ConversionWorker | Dönüşümü GUI thread'inden ayırır ve sayfa düzeyinde iptal sinyali taşır. | `uygulama/app/gui/workers/conversion_worker.py` |
| Dönüşüm servisi | Pipeline, builder ve validator'ı tek servis sözleşmesinde birleştirir. | `uygulama/app/core/converter.py` |
| ConversionPipeline | PDF sayfalarını okur, görselleri geçici alana çıkarır, OCR ve layout analizini koordine eder. | `uygulama/app/core/pipeline.py` |
| Alan modelleri | Kaynak blokları ve anlamsal belgeyi formatlar arası taşıyan dataclass modellerini sağlar. | `uygulama/app/core/models.py` |
| PDF okuyucu/ayrıştırıcı | PDF açma, parola doğrulama, üstveri, koordinatlı metin ve görsel çıkarımı yapar. | `uygulama/app/pdf/` |
| OCR motoru | Tesseract bulunabilirliğini kontrol eder, 300 DPI sayfa render'ı ve TSV metin çıkarımı yapar. | `uygulama/app/ocr/engine.py` |
| Layout analyzer | Okuma sırası, üst/alt bilgi, sayfa numarası, başlık, paragraf, liste, tablo, dipnot, bölüm ve açıklamaları algılar. | `uygulama/app/layout/` |
| EPUB builder | SemanticDocument'ı XHTML, OPF, nav, CSS ve görsel varlıkları içeren EPUB 3 ZIP'ine dönüştürür. | `uygulama/app/epub/builder.py` |
| EPUB validator | ZIP sırası, mimetype, container, manifest/spine, XML ve yerel referansları doğrular. | `uygulama/app/epub/validator.py` |
| Windows bootstrapper | Güncel kaynak arşivini indirir, runtime'ı hazırlar ve GUI'yi başlatır. | `PDFtoEPUB.cmd`, `uygulama/baslat*.ps1` |

## Veri Akışı

1. `run.py`, GUI/CLI çağrısını seçer; CLI veya GUI bir girdi PDF'si ve seçenekler oluşturur.
2. `PdfToEpubConverter` yolları çözer, PDF'nin varlığını kontrol eder ve varsayılan seçenekleri tamamlar.
3. `PdfReader` PyMuPDF ile PDF'yi açar, varsa kullanıcı parolasını doğrular ve PDF üstverisini okur.
4. `PageParser`, her sayfadan koordinatlı metin satırlarını çıkarır; görseller `ImageExtractor` tarafından geçici çalışma alanında hash ile tekilleştirilir.
5. Sayfa taranmış veya metinsiz görünüyorsa `OcrEngine`, 300 DPI render edilmiş görüntü üzerinde Tesseract TSV çıktısı üretir. Başarısız OCR durumunda seçeneklere göre sayfa görseli korunur, sayfa atlanır veya dönüşüm hatası verilir.
6. `HeuristicLayoutAnalyzer` tekrarlanan üst/alt bilgileri ve sayfa numaralarını filtreler; sütun okuma sırasını çözer ve blokları `SemanticDocument` içindeki içerik öğelerine dönüştürür.
7. Birinci seviye başlıklar bölüm sınırı olarak kullanılır. Her bölüm XHTML spine dosyasına yazılacak bir `Chapter` nesnesi olur.
8. `EpubBuilder`, geçici EPUB yapısını oluşturur, `mimetype` dosyasını ilk ve sıkıştırılmamış arşiv girdisi olarak yazar, görselleri optimize eder ve hedefe atomik olarak taşır.
9. `validate_epub`, oluşturulan hedefi doğrular; rapor ve ilerleme callback'i sonuçları CLI/GUI'ye iletir.

## Entegrasyonlar

- PyMuPDF, PDF iç yapısına ve sayfa geometrisine erişim sağlar.
- Pillow, OCR ön işleme, görsel format dönüşümü ve görsel optimizasyonu sağlar.
- Tesseract, yalnızca makinede kurulu bir executable ve dil modeli üzerinden çağrılır.
- PySide6, GUI, worker thread, dosya URL'leri, ayarlar ve Windows masaüstü entegrasyonunu sağlar.
- GitHub yalnızca Windows bootstrapper'ın kaynak/runtime indirmelerinde kullanılır; dönüşüm pipeline'ı uzak servise bağlı değildir.
- Veritabanı veya kullanıcı hesabı entegrasyonu yoktur.

## Sınırlar ve Değişmezler

- PDF ayrıştırma katmanı ile EPUB yazma katmanı doğrudan birbirine bağlanmaz; aradaki sözleşme `SemanticDocument` ve ilgili dataclass modelleridir.
- Kaynak PDF okunur ve değiştirilmez. Geçici görseller ve ara çıktılar geçici dizinlerde tutulur.
- Hedef EPUB geçici arşivden atomik olarak yayımlanır; mevcut hedef dosyanın değişebileceği davranışı korunmalıdır.
- EPUB arşivinde `mimetype` ilk ve sıkıştırılmamış girdi olmalıdır; container, OPF manifest/spine ve yerel XHTML referansları geçerli olmalıdır.
- Layout sezgileri kayıplı olduğundan yeni algılayıcı değişiklikleri mevcut metin ve yerleşim testleriyle doğrulanmalıdır.
- GUI işi ana Qt event loop'unda çalıştırılmamalı; iptal callback'i sayfa sınırları arasında kontrol edilmelidir.
- Dönüşüm yerel çalışır; uygulama katmanına zorunlu ağ veya uzak OCR bağımlılığı eklenmemelidir.

## Mimari Kararlar

Kalıcı bir mimari karar eklendiğinde `docs/decisions/` altında numaralı ADR oluşturulur. `docs/decisions/000-template.md` yalnızca ADR şablonudur; henüz projeye özel numaralı ADR bulunmamaktadır. Mevcut mimari davranışın kısa özeti:

- PDF ayrıştırma, layout analizi ve EPUB yazımı format bağımsız ara model üzerinden ayrıştırılmıştır.
- Dönüşüm yerel, deterministik sezgilerle ve kayıplı görsel düzen yerine yeniden akışlı anlamsal içerik hedefiyle çalışır.
