# Proje İlerlemesi

Bu dosya oturumlar arasında değişen çalışma durumunu tutar. Kalıcı kurallar `AGENTS.md` ve `docs/` altındaki bağlam dosyalarında tutulur.

## Güncel Durum

- Son güncelleme: `2026-08-10`
- Güncel hedef: Uygulama ve mevcut davranışla uyumlu kök/dokümantasyon Markdown dosyalarını doldurmak.
- Durum: `DOKÜMANTASYON TAMAMLANDI`
- Aktif dal/çalışma alanı: `main` / `C:\Users\ATY\Documents\PROJECTS\PDFtoEPUB`
- Çalışma ağacı notu: `.gitignore` içindeki mevcut kullanıcı değişikliği korunmaktadır; generated cache dosyaları kaynak değişikliği değildir.

## Önceki Oturum Özeti

### Tamamlananlar

- PDF→EPUB pipeline'ında başlık, paragraf, diyalog, dipnot, OCR ve görsel işleme davranışları iyileştirildi.
- CLI, GUI ve `PdfToEpubConverter.convert()` ortak servis akışı korunarak EPUB 3 üretimi ve dahili doğrulama tamamlandı.
- Değişiklikler `49aaf50 Fix PDF text layout reconstruction` commit'i ile `origin/main` dalına gönderildi.
- Bu oturumda README, ürün/teknik/mimari/konvansiyon dokümanları, AGENTS sınırları ve görev takibi dolduruldu.

### Doğrulamalar

- Önceki uygulama oturumunda 67 pytest testi başarılı oldu.
- Önceki uygulama oturumunda `ruff check app tests` başarılı oldu.
- Önceki uygulama oturumunda GUI smoke kontrolü başarılı oldu.
- Önceki commit öncesinde `git diff --check` hatasızdı; yalnızca satır sonu dönüşümü uyarıları görüldü.
- Bu dokümantasyon oturumunda proje Markdown dosyaları ve gerçek giriş noktaları kodla karşılaştırıldı; `docs/decisions/000-template.md` bilerek yeniden kullanılabilir şablon olarak bırakıldı.
- Placeholder taramasında yalnızca bu ADR şablonundaki `TBD` alanları kaldı.
- `git diff --check` boşluk hatası bildirmedi; mevcut `.gitignore` dosyası için satır sonu dönüşüm uyarısı görüldü.

### Kararlar

- PDF ayrıştırma, sezgisel layout analizi ve EPUB üretimi `SemanticDocument` ara modeliyle ayrıştırılmıştır.
- Dönüşüm yerel çalışır; OCR gerekiyorsa Tesseract ve Türkçe modeli yerel olarak kullanılır.
- `docs/decisions/000-template.md` proje kararı değil, yeni ADR'ler için şablon olarak korunur.

### Açık Sorular ve Engeller

- `pyproject.toml` Python `>=3.12` isterken Windows bootstrapper `>=3.11` runtime bulmayı kabul ediyor; gerçek 3.11 uyumluluğu doğrulanmadı.
- Paketlenmiş dağıtımda ikon ve tüm package-data dosyalarının dahil edildiği doğrulanmadı.
- CI, resmi release süreci, lisans ve desteklenen işletim sistemi matrisi tanımlı değil.
- Harici `epubcheck` normal dönüşüm/test bağımlılığı değil.

## Sonraki Adımlar

1. Python sürüm şartını bootstrapper ile hizala veya 3.11 desteğini açıkça reddet.
2. Paketlenmiş kurulumda CLI giriş noktası, ikon ve runtime dosyalarını doğrula.
3. CI ve GUI/bootstrap smoke kapsamını proje ihtiyacına göre ekle.

## Oturum Günlüğü

### 2026-08-10

- Proje kökündeki ve `docs/` altındaki Markdown dosyaları incelendi.
- README ürün kullanımına göre yeniden yazıldı; ürün, teknik bağlam, mimari ve konvansiyon dosyaları gerçek kodla dolduruldu.
- `AGENTS.md` içindeki proje sınırları ve korunan API'ler somutlaştırıldı.
- `TODO.md` açık teknik riskler ve tamamlanan dokümantasyon işiyle güncellendi.

Eski kayıtlar biriktikçe `docs/history/` altına taşınabilir; tarihsel kayıtlar silinmez.
