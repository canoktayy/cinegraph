# Buradan başla

Proje klasöründe terminal aç. Docker Desktop çalışır durumda olsun.

```bash
make install
make setup
make docker-run
make download seed analytics
```

- Arayüz: http://localhost:18080
- Swagger: http://localhost:18080/docs
- Neo4j Browser: http://localhost:17474
- Yerel model: LM Studio'da qwen2.5-7b-instruct; server port 1234

Veri/öneriler model kapalıyken de çalışır. Doğal dil sorgusu için model server açık olmalı; arayüzdeki şifreli alana `.env` içindeki `APP_API_KEY` değerini gir. Bu alanın değeri kaydedilmez veya GitHub'a gönderilmez. Neo4j şifresi de aynı yerel dosyadadır. Anahtarları ekran görüntüsüne veya Git'e ekleme.

Kullanıcı 42 ile önerileri aç; “Why this film?” düğmesi gerçek kanıt yollarını gösterir. “Taste communities” topluluk keşfidir. Katalog aramasında `Toy Story` denenebilir. “The long view” günümüzün popüler filmleri değil, tarihsel veri görünümüdür.

Kalite kontrolü: `make lint`, `make test`, `make demo`. Tüm sonuçlar ve sınırlılıklar `docs/results.md` içindedir. Notebook `demo.ipynb`, ayrıntılı proje rehberi `proje_guide.pdf`.

Kapatmak için `make stop`; veri saklanır. Normal kullanımda `docker compose down -v` çalıştırma. Başka bir bilgisayarda özel repoyu klonlamak için kendi GitHub yetkin gerekir; ek Neo4j veya ücretli LLM hesabı gerekmez.

Repo ve image özel tutulur. Hocanın herkese açık registry ve bağımsız insan incelemesi/grup çalışması ölçütlerinin uygulanışı ayrıca netleştirilmelidir; tamamlanmış gibi gösterilmez.

## Yeni ziyaretçi için kişisel öneri

1. **Find my films** düğmesine bas.
2. On tur boyunca her beşli gruptan en sevdiğin filmi seç. Tanımadığın grubu **skip round** ile geç; **Back** ile geri dönebilirsin.
3. Son turdan sonra **Your next watch** listesi senin seçimlerinden hesaplanır. Tür filtresiyle daraltabilirsin.
4. **Why this film?** hangi seçtiğin filmlerin öneriye katkı verdiğini ve kaç ortak olumlu puanlayan izleyici olduğunu gösterir.

Bu akışta API anahtarı ve LLM gerekmez. Seçimler sayfa yenilenince sıfırlanır; kullanıcı hesabı açılmaz ve MovieLens verisine yeni puan yazılmaz. Seçmediğin filmler beğenmediğin varsayılmaz. Eski kullanıcı numarasıyla gösterim için **Explore the research demo instead** kullanılır. Doğal dil paneli hocaya gösterim için açılır menüdedir.
