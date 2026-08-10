# Proje Kuralları

Bu belge kod, test, dokümantasyon ve Git çalışmalarında izlenecek proje kurallarını tanımlar.

## Kod

- Dil ve tip güvenliği: Python 3.12 hedeflenir; public ve modül içi fonksiyonlarda mümkün olduğunca type hint kullanılır. Modüller `from __future__ import annotations` desenini izler.
- Adlandırma: Modül ve fonksiyonlar `snake_case`, sınıflar `PascalCase`, sabitler `UPPER_SNAKE_CASE`, özel yardımcılar başında `_` olacak şekilde adlandırılır.
- Veri modelleri: `dataclass`, küçük ve taşıma amaçlı modellerde `slots=True`; değişmez modellerde `frozen=True` kullanılır.
- Dosya yapısı: PDF, OCR, layout, EPUB, GUI ve core sorumlulukları kendi paketlerinde tutulur. EPUB katmanı PDF kütüphanesine doğrudan bağlanmaz.
- İş akışı: Yeni davranış mevcut pipeline ve semantic model üzerinden eklenir; aynı sorumluluğu yapan yeni bir paralel soyutlama oluşturulmaz.
- Hata yönetimi: Kullanıcıya sunulabilir beklenen hatalar `ConversionError` ve alt sınıflarıyla ifade edilir. Üçüncü taraf kütüphane hataları uygun uygulama hatasına çevrilir veya açık bir uyarıyla raporlanır; hatalar sessizce yutulmaz.
- Dosya davranışı: Girdi PDF'si değiştirilmez. Geçici dosyalar `TemporaryDirectory` veya belirlenmiş geçici çalışma alanlarında tutulur. EPUB hedefi atomik yayınlanır.
- Logging: Ortak log kurulumu `app.core.logging.configure_logging` üzerinden yapılır. Loglar zaman, seviye, logger adı ve mesaj içerir; parola, token veya hassas içerik yazılmaz.
- Dokümantasyon: Modül, sınıf ve karmaşık public fonksiyonlarda kısa docstring kullanılır. Yorumlar yalnızca kodun niyetini açıklamak gerektiğinde eklenir.
- Formatlama: Ayrı formatter yapılandırılmamıştır. Ruff kontrolü kaynak biçiminin temel kalite kapısıdır; gereksiz biçimsel refactor yapılmaz.

## Test

- Test framework: pytest.
- Test konumu: `uygulama/tests/test_*.py`; pytest `testpaths = ["tests"]` ayarını kullanır.
- Fixture yaklaşımı: `tests/conftest.py` sentetik PDF ve model yardımcıları sağlar. İkili PDF fixture'ları repository'ye eklenmez.
- Minimum beklenti: Yeni davranış için en az bir birim veya uygun entegrasyon testi eklenir; ilgili tüm testler ve `ruff check app tests` çalıştırılır.
- Test kapsamı: CLI, PDF üstverisi, OCR, görsel ayıklama, başlık/bölüm/sütun, paragraf, sayfa numarası, üst/alt bilgi, dipnot, çıktı adlandırma, EPUB üretimi ve dahili EPUB doğrulaması kapsanır.
- Entegrasyon testi: `PdfToEpubConverter` ile sentetik PDF'den gerçek EPUB üretimi ve `validate_epub` kontrolü kullanılır. Harici `epubcheck` test bağımlılığı değildir.
- GUI/launcher testi: `python run.py --smoke-test` temel GUI yaşam döngüsünü doğrular; gerçek Windows indirme ve Tesseract kurulumu otomatik test kapsamının dışındadır.

## Git

- Ana dal: `main`. Ayrı özellik veya hata düzeltme dalları için repository'de zorunlu bir adlandırma şablonu tanımlı değildir; kullanılan dal amacı anlaşılır biçimde adlandırılmalıdır.
- Commit formatı: Kısa, emir kipinde ve değişikliği anlatan mesajlar kullanılır. Repository geçmişindeki mesajlar İngilizce ve kısa fiil öbekleridir; Conventional Commits zorunlu değildir.
- Pull request beklentisi: Zorunlu PR şablonu veya CI kapısı yoktur. PR açılırsa davranış değişikliği, test sonucu ve dokümantasyon etkisi açıklanmalı; yalnızca ilgili dosyalar dahil edilmelidir.
- Commit/push yetkisi: Kullanıcı açıkça istemeden commit veya push yapılmaz.
- Çalışma ağacı: Kullanıcının mevcut değişiklikleri korunur; ilgili olmayan dosyalar stage edilmez ve geri alınmaz.

## Dokümantasyon

- Yeni kalıcı teknik veya mimari karar için `docs/decisions/` altında numaralı ADR oluşturulur. `000-template.md` şablon olarak korunur.
- Kullanıcıya görünen davranış, CLI seçeneği, GUI akışı veya bağımlılık değişirse ilgili README/context dosyası aynı değişiklikte güncellenir.
- Oturum durumu, doğrulama sonuçları ve geçici engeller `PROGRESS.md` içine yazılır.
- Açık işler küçük, tek sonuçlu ve kabul ölçütü doğrulanabilir şekilde `TODO.md` içinde tutulur; tamamlanan işler silinmez.
- Kod örnekleri gerçek giriş noktaları ve komutlarla eşleşmelidir. Doğrulanmamış davranış kesin gerçek gibi yazılmaz.
