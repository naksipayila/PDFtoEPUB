# Görev Listesi

Görevler küçük, tek sonuçlu ve doğrulanabilir kabul ölçütlerine sahip olmalıdır.

## Yüksek Öncelik

- [ ] Python sürüm şartını bootstrapper ile hizala.
  - Kabul ölçütü: `pyproject.toml` ve `baslat.ps1` aynı minimum Python sürümünü kullanır; desteklenmeyen bir sürüm için davranış test veya açık hata ile belgelenir.
  - Öncelik: High
  - Durum: Pending
  - Engelleyen neden: None

## Normal Öncelik

- [ ] Paketlenmiş dağıtım içeriğini doğrula.
  - Kabul ölçütü: Temiz bir ortamda paket kurulumu veya build çıktısı CLI giriş noktasını, uygulama paketlerini ve `assets/pdf-to-epub.ico` dosyasını beklenen şekilde içerir.
  - Öncelik: Normal
  - Durum: Pending
  - Engelleyen neden: Projede doğrulanmış build/release komutu yok.

- [ ] Temel CI kalite akışını ekle veya bilinçli olarak kapsam dışı bırakma kararı yaz.
  - Kabul ölçütü: pytest ve Ruff komutları otomatik çalışır veya neden çalıştırılmadığı numaralı ADR/README ile açıklanır.
  - Öncelik: Normal
  - Durum: Pending
  - Engelleyen neden: CI sağlayıcısı ve release hedefi seçilmedi.

- [ ] GUI ve Windows bootstrapper için otomatik smoke kapsamını genişlet.
  - Kabul ölçütü: GUI dönüşüm worker'ı, iptal akışı ve hazır/eksik runtime dispatch davranışı en azından uygun mock veya Windows smoke testiyle doğrulanır.
  - Öncelik: Normal
  - Durum: Pending
  - Engelleyen neden: Gerçek Windows/Tesseract kurulum ortamı CI'da mevcut değil.

## Düşük Öncelik / Fikirler

- [ ] Desteklenen Windows/Python sürümleri ve lisans bilgisini kesinleştir.
  - Kabul ölçütü: README ve teknik bağlamda destek matrisi ile lisans dosyası/kararı bulunur.
  - Öncelik: Low
  - Durum: Pending
  - Engelleyen neden: Ürün sahibi kararı gerekiyor.

- [ ] Harici `epubcheck` kalite kontrolünü isteğe bağlı geliştirme adımı yap.
  - Kabul ölçütü: Kurulu `epubcheck` ile çalışan, kurulmadığında açıkça atlanan bir doğrulama komutu ve dokümantasyonu olur.
  - Öncelik: Low
  - Durum: Pending
  - Engelleyen neden: Java/epubcheck dağıtım tercihi yapılmadı.

## Tamamlananlar

- [x] PDF metin/layout yeniden yapılandırmasını ve ilgili testleri tamamla.
  - Kabul ölçütü: Başlık, diyalog, paragraf, dipnot, OCR ve EPUB davranışları test edilir.
  - Öncelik: High
  - Durum: Completed
  - Engelleyen neden: None; commit `49aaf50`.

- [x] Kök ve `docs/` Markdown dosyalarını mevcut uygulamaya göre doldur.
  - Kabul ölçütü: README, AGENTS sınırları, PROGRESS, TODO ve dört ana context dosyası gerçek kodla uyumlu açıklamalar içerir.
  - Öncelik: High
  - Durum: Completed
  - Engelleyen neden: None; 2026-08-10.

## Görev Kuralları

- Kabul ölçütü doğrulanmadan görev tamamlandı olarak işaretlenmez.
- Engellenen görevde neden ve gerekli karar aynı görev altında belirtilir.
- Büyük işler daha küçük görevlere ayrılır.
- Tamamlanan görevler silinmez; geçmiş korunur.
