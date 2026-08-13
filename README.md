# PDFtoEPUB

PDFtoEPUB, yerel PDF dosyalarını yeniden akışlı EPUB 3 kitaplarına dönüştüren, Python ile yazılmış bir masaüstü uygulamasıdır. PDF'nin metin katmanını, sayfa geometrisini, temel düzen bilgisini, belge üstverisini, seçili görselleri ve gerektiğinde yerel Tesseract OCR çıktısını analiz eder.

Dönüşüm işlemi kurulum tamamlandıktan sonra yerel çalışır. Windows başlatıcısı ilk kurulumda GitHub, Python, Tesseract ve Türkçe OCR verilerini indirebildiği için başlatıcıyı kullanırken internet bağlantısı gerekir.

## Durum

- Sürüm: `0.1.0`
- Paket adı: `pdf-to-epub`
- Birincil kullanım: Windows üzerinde GUI ile sürükle-bırak dönüşüm
- Alternatif kullanım: CLI ve `PdfToEpubConverter` Python servisi
- EPUB standardı: EPUB 3, yeniden akışlı içerik

## Özellikler

- PDF metnini koordinatlarını koruyarak ayıklar ve anlamsal belge modeline dönüştürür.
- Başlık, bölüm, paragraf, liste, temel pipe-ayraçlı tablo, resim açıklaması ve dipnot algılamayı dener.
- Çok sütunlu sayfalarda okuma sırasını düzenler.
- Basılı "İçindekiler" sayfalarındaki tek/çok sütunlu kayıtları, noktalı liderleri, ayrı sayfa etiketlerini ve satıra sarılmış başlıkları yeniden akışlı EPUB satırlarına dönüştürür.
- Tekrarlanan üstbilgi/altbilgileri ve sayfa kenarındaki sayfa numaralarını varsayılan olarak kaldırır.
- Güvenilir seçilebilir PDF metnini korur; yalnız metin yoksa, görünmezse veya bozuk Unicode içeriyorsa yerel Tesseract OCR kullanır.
- OCR yön/eğiklik düzeltmesi, iki sayfa segmentasyon adayı, zaman aşımı ve güven/kapsam karşılaştırması uygular. Varsayılan OCR dili `tur` dilidir.
- Düşük güvenli OCR, görsel fallback ve metin kaynağını sayfa bazlı kalite raporunda gösterir.
- OCR ile kurtarılamayan raster veya vektör sayfaları sessizce atmak yerine tam sayfa görseli olarak korur.
- İlk sayfayı basit kapak sezgisiyle algılayıp EPUB kapak görseli olarak ekleyebilir.
- Görselleri SHA-256 ile tekilleştirir ve isteğe bağlı olarak EPUB içine optimize ederek yazar.
- EPUB adayını hedefe dokunmadan oluşturur ve doğrular; yalnız geçerliyse hedefi atomik olarak değiştirir.
- Dahili validator; manifest/spine/nav, dil, XHTML ve fragment hedeflerini kontrol eder. İsteğe bağlı EPUBCheck ve CI Calibre round-trip kalite kapıları bulunur.
- CLI ve GUI aynı `PdfToEpubConverter` servisini kullanır.
- GUI dönüşümü ayrı Qt iş parçacığında çalıştırır, sayfa sınırlarında iptal desteği sunar ve pencere kapanırken worker'ın güvenli biçimde bitmesini bekler.
- GUI, özgün PDF sayfasını ve kaynak sayfaya bağlı EPUB metnini yan yana gösteren düzeltme ekranı sağlar; düşük güvenli OCR sayfalarını otomatik açar.

## Gereksinimler

### Doğrudan Python kurulumu

- Python `>=3.12` (`uygulama/pyproject.toml` içindeki paket şartı)
- Runtime paketleri: PySide6, PyMuPDF, Pillow ve pytesseract
- Geliştirme için pytest ve Ruff
- Taranmış PDF'ler için Tesseract executable dosyası ve `tur.traineddata`

### Windows başlatıcısı

Kök dizindeki `PDFtoEPUB.cmd`, uygulamayı `%LOCALAPPDATA%\PDFtoEPUB` altında hazırlar. Başlatıcı:

1. GitHub `main` dalının güncel ZIP arşivini indirir.
2. Uygulama dosyalarını yerel uygulama dizinine kopyalar.
3. Kullanılabilir Python bulamazsa Python `3.12.10` paketini indirir.
4. Python 3.12'den eski bir sanal ortamı yeniler, ardından `runtime-requirements.txt` dosyasını kurar.
5. Tesseract ile sabit revision'dan `tessdata_best` Türkçe ve yön algılama modellerini hazırlar.
6. PySide6 GUI'yi başlatır.

Bu akış yalnızca Windows PowerShell içindir. Arşiv sabit bir commit veya checksum ile pinlenmediğinden başlatıcı her çalıştırıldığında GitHub'daki güncel `main` içeriğini alabilir.

## Yerel Kurulum

Komutları `uygulama` dizininde çalıştırın:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

OCR kullanılmayacaksa doğrudan PDF metin katmanıyla da çalışılabilir. Taranmış belgeler için Tesseract kurulumu ve `tur.traineddata` ayrıca gereklidir. Sanal ortamı etkinleştirmeden çalıştırmak için `.venv\Scripts\python.exe` kullanılabilir.

## Kullanım

### GUI

```powershell
python run.py
```

GUI'ye yerel bir `.pdf` dosyasını bırakınca dönüşüm otomatik başlar. Çıktı sistemin İndirilenler klasörüne, PDF üstverisindeki başlıktan veya dosya adından türetilen `<başlık>-EPUB.epub` adıyla yazılır. GUI'de Türkçe OCR, kapak çıkarımı ve okuyucu CSS'i açıktır; satır içi görseller kapalıdır. Dönüşümden sonra `Metni Gözden Geçir` ile kaynak PDF sayfası ve EPUB metni yan yana açılır. Düşük güvenli OCR varsa bu ekran otomatik olarak ilgili sayfada açılır. Kaydedilen düzeltme yeniden doğrulanır ve atomik yayımlanır.

GUI smoke kontrolü için:

```powershell
python run.py --smoke-test
```

### CLI

```powershell
python run.py INPUT.pdf -o OUTPUT.epub
```

Paket giriş noktasını kurmak için `uygulama` dizininde editable kurulum yapın:

```powershell
python -m pip install -e ".[dev]"
python -m app INPUT.pdf --output OUTPUT.epub
pdf-to-epub INPUT.pdf --output OUTPUT.epub
```

Yukarıdaki iki komut `uygulama` dizininde çalıştırılmalıdır. Başlıca seçenekler:

| Seçenek | Varsayılan davranış | Açıklama |
| --- | --- | --- |
| `-o`, `--output PATH` | Girdi adı + `.epub` | Çıktı yolunu belirler; uzantı `.epub` yapılır. |
| `--ocr` / `--no-ocr` | OCR açık | Taranmış veya metinsiz sayfalarda yerel OCR kullanır. |
| `--ocr-language CODE` | `tur` | Tesseract dilini veya `tur+eng` gibi birleşimi belirler. |
| `--language TAG` | `tr` | EPUB için geçerli BCP 47 yayın dili belirler. |
| `--include-images` / `--no-images` | Görsel kapalı | Metin sayfalarındaki görselleri EPUB'a ekler. |
| `--keep-page-numbers` | Sayılar kaldırılır | Kenar sayfa numaralarını korur. |
| `--keep-header-footer` | Üst/alt bilgiler kaldırılır | Tekrarlanan kenar metinlerini korur. |
| `--no-table-detection` | Temel tablo algılama açık | Pipe-ayraçlı tablo tanımayı kapatır. |
| `--no-columns` | Sütun algılama açık | Çok sütunlu okuma sırası düzenlemesini kapatır. |
| `--no-cover` | Kapak çıkarımı açık | İlk sayfa kapak görselini kapatır. |
| `--password PASSWORD` | Parola yok | Şifreli PDF için kullanıcı parolasını verir. |
| `--title`, `--author`, `--publisher`, `--subject` | PDF üstverisi | EPUB üstverisini komut satırından geçersiz kılar. |
| `--debug-dir DIRECTORY` | JSON yok | Sayfa bloklarını hata ayıklama JSON'u olarak yazar. |
| `--epubcheck` | Kapalı | Kurulu EPUBCheck ile ek doğrulama yapar; araç yoksa açık hata verir. |
| `--verbose` | Normal log | Konsol log seviyesini ayrıntılı yapar. |

CLI varsayılan olarak çıktı dizinine `pdf_to_epub.log` yazar. Var olan çıktı dosyası onay sorulmadan değiştirilebilir.

## Geliştirme

`uygulama` dizininde:

```powershell
python -m pytest
ruff check app tests
```

Testler ikili PDF fixture'ları yerine geçici ve sentetik PDF'ler üretir. Ruff ayarları `pyproject.toml` içindedir. GitHub Actions; Windows/Linux pytest ve Ruff, GUI smoke, checksum ile sabitlenmiş EPUBCheck 5.3.0, Calibre reader round-trip ve Python 3.12 clean-wheel kurulumunu doğrular.

## Günlükler ve Hata Ayıklama

- CLI logu: çıktı dosyasının bulunduğu dizin, `pdf_to_epub.log`
- GUI logu: `%USERPROFILE%\.pdf_to_epub\pdf_to_epub.log`
- Ham sayfa blokları: CLI `--debug-dir` seçeneğiyle verilen dizinde `page_001.json` biçiminde; metin kaynağı, OCR güveni ve kalite sorunları da kaydedilir.
- EPUB doğrulaması: ZIP yapısı, `mimetype`, `container.xml`, metadata/dil, tekil OPF manifest/spine/nav, XHTML ve yerel/fragment referansları dahili olarak kontrol edilir.
- Harici EPUBCheck normal dönüşümde çalıştırılmaz; `--epubcheck` ile zorunlu tutulabilir ve CI'da sabit sürümle çalışır.

## Proje Yapısı

```text
.
├── PDFtoEPUB.cmd                 # Windows indirme ve başlatma zinciri
├── AGENTS.md                     # Kalıcı çalışma kuralları
├── PROGRESS.md                   # Oturumlar arası geçici durum
├── TODO.md                       # Küçük ve doğrulanabilir işler
├── docs/                         # Ürün, teknik ve mimari dokümantasyon
└── uygulama/
    ├── run.py                    # GUI/CLI ortak giriş noktası
    ├── baslat.ps1                # Python, sanal ortam ve OCR hazırlığı
    ├── baslat-dispatch.ps1       # Hazır runtime veya kurulum seçimi
    ├── pyproject.toml            # Paket ve araç ayarları
    ├── app/
    │   ├── core/                 # Pipeline, modeller, seçenekler ve hatalar
    │   ├── pdf/                  # PDF okuma, metin, üstveri ve görsel ayıklama
    │   ├── ocr/                  # Tesseract adaptörü
    │   ├── layout/               # Düzen ve anlamsal öğe algılama
    │   ├── epub/                 # EPUB üretimi, CSS ve doğrulama
    │   └── gui/                  # PySide6 arayüzü ve worker
    └── tests/                    # pytest testleri
```

## Sınırlamalar

- PDF görsel düzeni birebir yeniden çizilmez; sonuç sezgisel ve yeniden akışlıdır.
- Başlık algılama en fazla dört seviye için sezgiseldir ve yanlış pozitifleri azaltmak için tutucu eşikler kullanır.
- Sütun algılama en fazla üç sütunu destekler.
- Tablo algılama yalnızca temel pipe-ayraçlı metin tablolarını tanır; geometrik tablolar genel olarak yeniden kurulmaz.
- PDF bağlantıları, vektör çizimleri, açıklamalar, formlar ve benzeri yapılar korunmaz.
- Dipnotlar EPUB `aside` öğeleri olarak yazılır; kaynak metin içi dipnot işaretiyle otomatik bağlantı kurulmaz.
- GUI OCR dili `tur` olarak sabittir; CLI `--ocr-language` ile kurulu modelleri seçebilir.
- Yalnızca görsel/vektör içeren sayfalar yeniden akışlı metin yerine sayfa görseli olarak korunabilir.
- GUI şifreli PDF'ler için parola alamaz; CLI `--password` seçeneğini destekler.
- GUI'de satır içi görseller kapalıdır; CLI'de `--include-images` ile açılabilir.

## Dokümantasyon

- [`docs/product-context.md`](docs/product-context.md): ürün amacı, kullanıcılar ve kapsam
- [`docs/tech-context.md`](docs/tech-context.md): kurulum, komutlar, bağımlılıklar ve operasyon
- [`docs/architecture.md`](docs/architecture.md): bileşenler ve veri akışı
- [`docs/conventions.md`](docs/conventions.md): kod, test, Git ve dokümantasyon kuralları
- [`PROGRESS.md`](PROGRESS.md): güncel oturum durumu
- [`TODO.md`](TODO.md): açık ve tamamlanan işler

## Güvenlik ve Veri Davranışı

- Girdi PDF'si uygulama tarafından okunur; kaynak dosya değiştirilmez.
- Şifreler yalnızca komut satırı argümanı olarak alınır; dokümantasyona veya loglara eklenmemelidir.
- `.env` ve benzeri gizli dosyalar commit edilmez.
- Çıktı yolu mevcut bir EPUB'ı yalnız yeni aday doğrulamadan geçtikten sonra atomik olarak değiştirir.
