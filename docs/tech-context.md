# Teknik Bağlam

Bu belge PDFtoEPUB'nin geliştirme, çalıştırma ve dağıtım bilgilerini içerir. Yeni bağımlılık, komut veya teknik kısıt eklendiğinde güncellenir.

## Teknoloji

- Dil ve runtime: Python `>=3.12`.
- Ana framework: PySide6. GUI `QMainWindow`, `QThread`, `QSettings` ve Qt'nin masaüstü servislerini kullanır.
- PDF motoru: PyMuPDF (`pymupdf` import adı `fitz`).
- Görsel işleme: Pillow.
- OCR adaptörü: pytesseract üzerinden yerel Tesseract executable.
- Paketleme: `pyproject.toml`, setuptools build backend ve pip.
- Veritabanı: None. Uygulama kalıcı veritabanı kullanmaz.
- Test framework: pytest.
- Lint: Ruff. Yapılandırma `uygulama/pyproject.toml` içindedir.
- Sürüm: `0.1.0` (`uygulama/app/__init__.py`).

Runtime bağımlılıkları `runtime-requirements.txt`, runtime ve geliştirme bağımlılıkları `requirements.txt` içinde tutulur. `pyproject.toml` içindeki `dev` extra'sı pytest ve Ruff'u tanımlar.

## Dizinler ve Giriş Noktaları

- Uygulama kodu: `uygulama/app/`
- Testler: `uygulama/tests/`
- Python paket ayarı: `uygulama/pyproject.toml`
- Runtime bağımlılık listesi: `uygulama/runtime-requirements.txt`
- Geliştirme bağımlılık listesi: `uygulama/requirements.txt`
- GUI/CLI ortak giriş noktası: `uygulama/run.py`
- CLI modülü: `uygulama/app/cli.py`
- GUI bootstrap: `uygulama/app/main.py`
- Windows başlatma zinciri: `PDFtoEPUB.cmd`, `uygulama/baslat-dispatch.ps1`, `uygulama/baslat.ps1`
- Dokümantasyon: kök Markdown dosyaları ve `docs/`

## Yaygın Komutlar

Aşağıdaki Python komutları `uygulama` dizininde çalıştırılır.

```text
Kurulum:        python -m venv .venv
Bağımlılıklar:  python -m pip install -r requirements.txt
Runtime:        python -m pip install -r runtime-requirements.txt
GUI:            python run.py
CLI:            python run.py INPUT.pdf -o OUTPUT.epub
Modül CLI:      python -m app INPUT.pdf [OPTIONS]
Test:           python -m pytest
Lint:           ruff check app tests
Smoke:          python run.py --smoke-test
Format:         Not configured
```

`pyproject.toml` setuptools build backend tanımlar, ancak `build` paketi bağımlılıklara eklenmiş veya doğrulanmış değildir. Paket üretimi gerektiğinde ayrıca `build` kurulup `python -m build` komutu kullanılabilir; bu henüz proje release sürecinin parçası değildir.

## Ortam ve Yapılandırma

- Zorunlu uygulama ortam değişkeni: None. Normal vektör metinli PDF dönüşümü için `.env` dosyası gerekmez.
- `PDFTOEPUB_TESSERACT`: Tesseract executable yolunu açıkça belirler.
- `TESSDATA_PREFIX`: Tesseract dil verilerinin bulunduğu dizini belirtir; Türkçe OCR için `tur.traineddata` bulunmalıdır.
- OCR dili: CLI ve GUI tarafından `tur` olarak belirlenir.
- Yerel geliştirme gereksinimleri: Python `>=3.12`, pip, runtime paketleri; OCR testleri ve taranmış PDF dönüşümleri için Tesseract ve Türkçe model.
- Gizli bilgi kaynağı: None. Proje kimlik bilgisi veya uzak API anahtarı kullanmaz. PDF parolası yalnızca CLI argümanı olarak alınır ve loglanmamalıdır.
- Ortamlar: Yerel geliştirme, yerel test ve son kullanıcı Windows kurulumu. Staging/production ortamı yoktur.

GUI logu `%USERPROFILE%\.pdf_to_epub\pdf_to_epub.log` altında, CLI logu ise çıktı dizinindeki `pdf_to_epub.log` dosyasında tutulur. `--debug-dir` verilirse ham sayfa blokları JSON olarak yazılır.

## Harici Servisler ve Entegrasyonlar

- Tesseract: Dönüşüm sırasında yerel process olarak çağrılır; uzak servise PDF gönderilmez. Harici bir kurulum yoksa taranmış sayfalar OCR olmadan işlenemez.
- GitHub: Yalnızca `PDFtoEPUB.cmd` başlatıcısı güncel `main.zip` ve PowerShell bootstrap akışının ihtiyaç duyduğu Python/Tesseract/Türkçe model dosyalarını indirmek için kullanır. Doğrudan dönüşümde GitHub çağrısı yoktur.
- PyMuPDF, Pillow, PySide6 ve pytesseract: Uygulamanın kurulu Python ortamındaki kütüphane entegrasyonlarıdır; kimlik doğrulama gerektirmez.

## Teknik Kısıtlar

- Kaynak `pyproject.toml` Python `>=3.12` ister. Windows bootstrapper kullanılabilir Python'ı `>=3.11` olarak kabul eden bir arama içerir; Python `3.11` ile gerçek uyumluluk doğrulanmamıştır. Bu iki şartın hizalanması açık bir teknik iştir.
- Düzen çıkarımı deterministik sezgilere dayanır; görsel PDF düzeni birebir korunmaz.
- Sütun algılayıcı en fazla üç sütun, başlık algılayıcı en fazla dört seviye destekler.
- Temel tablo algılama pipe-ayraçlı satırlarla sınırlıdır.
- EPUB çıktısı yeniden akışlıdır ve oluşturma sonunda dahili ZIP/XML/XHTML doğrulamasından geçer. Harici `epubcheck` normal akışta çalıştırılmaz.
- Dönüşüm geçici çalışma alanları kullanır; çıktı geçici dosyadan hedefe atomik olarak taşınır. Var olan hedef dosya değiştirilebilir.
- Uygulama yalnızca yerel dosyalarla çalışacak şekilde tasarlanmıştır. Resmi platform matrisi Windows başlatıcısı dışında belgelenmemiştir.
- Lisans dosyası, lockfile, CI yapılandırması ve resmi release pipeline'ı yoktur.

## Araç Kullanım Kuralları

- PDF'den metin, görsel ve üstveri çıkarımı `uygulama/app/pdf/` modülleri üzerinden yapılır; EPUB modülleri PDF kütüphanesi ayrıntılarını doğrudan kullanmamalıdır.
- OCR yalnızca `OcrEngine` üzerinden ve yerel Tesseract ile yapılır. Dönüşüm akışına uzak OCR servisi eklenmez.
- Yeni layout davranışları sentetik PDF veya model testleriyle doğrulanır; ikili fixture dosyaları testlere eklenmez.
- EPUB üretiminden sonra `validate_epub` dahili doğrulaması korunur. Harici `epubcheck` yalnızca ayrıca kuruluysa isteğe bağlı kalite kontrolüdür.
- Bootstrapper ağ erişimi kullanır; doğrudan yerel dönüşüm kodu ağ erişimine dayanmamalıdır.

## Dağıtım ve Operasyon

- Dağıtım yöntemi: Kök `PDFtoEPUB.cmd` GitHub `main` arşivini geçici dizine indirir, `uygulama` klasörünü `%LOCALAPPDATA%\PDFtoEPUB\uygulama` içine kopyalar ve PowerShell başlatıcıyı çalıştırır.
- Runtime kurulumu: `baslat.ps1` yerel `.runtime`, `.venv`, Tesseract ve Türkçe model hazırlığını yönetir.
- İzleme ve loglama: Merkezi izleme yoktur. Python logging konsola ve CLI/GUI log dosyalarına yazar; GUI son 500 log satırını gösterir.
- Rollback: Otomatik rollback mekanizması yoktur. Önceki uygulama arşivi veya `%LOCALAPPDATA%\PDFtoEPUB` altındaki bilinen çalışan runtime manuel olarak geri yüklenmelidir.
- Çıktı operasyonu: Kullanıcı tarafından verilen hedef EPUB üzerine yazılabilir; kaynak PDF korunur.

## Bağlam Güncelleme Kuralları

- Yeni bağımlılık, servis, komut veya teknik kısıt eklendiğinde bu dosya güncellenir.
- Bileşen ilişkileri ve veri akışı `docs/architecture.md` içinde tutulur.
- Geçici kurulum sorunları `PROGRESS.md` içine yazılır; kalıcı bilgiler çözüldüğünde buraya taşınır.
