# Buradan başla

**Cinegraph, sevdiğin filmleri seçmeni ister; ardından ne izleyebileceğini önerir ve her önerinin nedenini gösterir.** Hesap açman gerekmez. Seçimlerin yalnızca açık tarayıcı sekmesinde tutulur.

## 1. Uygulamayı çalıştır

Docker Desktop açıkken proje klasöründe şu komutları çalıştır:

```bash
make install
make setup
make docker-run
make download seed analytics
```

Ardından [siteyi aç](http://localhost:18080). [API belgeleri (Swagger)](http://localhost:18080/docs) ve [Neo4j Browser](http://localhost:17474) teknik inceleme içindir.

## 2. Menüde ne var?

Üst menü iki gruba ayrılır.

**Öneri al**

| Sayfa | Ne işe yarar? |
|---|---|
| Quick picks | Her turda beş film görürsün; on tur boyunca sevdiğini seçer ya da turu atlarsın. Model veya anahtar gerekmez. Sonuçlarda tür çipleriyle filtre uygulayabilir, **Why?** ile her önerinin nedenini görebilirsin. |
| Film assistant | Aynı akışın sohbetli hâlidir. Seçimlerden sonra “Bana sadece komedi öner” ya da “Fargo gibi filmler” yazarak sonuçları değiştirebilirsin. Yerel model gerekir. |

**Veriyi keşfet** (bu sayfalar senin seçimlerini kullanmaz)

| Sayfa | Ne işe yarar? |
|---|---|
| Catalog | 9.742 film içinde ada ve türe göre arama yaparsın. Bir filme tıklayınca aynı kişilerin sevdiği filmleri görürsün. |
| Top films | Veri setinin son yılında en yüksek puan alan filmleri ya da PageRank ile en merkezî filmleri listeler. |
| Dataset users | 610 anonim MovieLens kullanıcısından birini seçip ona yapılan önerileri ve topluluk (Louvain) keşfini görürsün. |
| Query lab | Doğal dilde sorduğun soru doğrulanmış bir Cypher sorgusuna dönüşür. Tehlikeli istekler 422 ile reddedilir. |

## 3. Film assistant'ı kullanmak

1. LM Studio'da **qwen2.5-7b-instruct** modelini yükle ve yerel sunucuyu **1234** portunda başlat.
2. **Film assistant** sayfasını aç. Anahtar girmen gerekmez. Sayfadaki gösterge modelin durumunu söyler: yeşil **Local model ready** ise hazırsın; değilse LM Studio'da neyi açman gerektiğini yazar, **check again** ile yeniden kontrol edebilirsin.
3. **Start the conversation** ile başla. Film kartına tıklayarak seç ya da turu atla. Kart tıklamaları sunucu tarafından yönetilir, bu yüzden hızlıdır. Modeli yalnızca yazdığın mesajlar kullanır.
4. On turdan sonra ya da **Recommend now** ile öneriler gelir. Bir afişe tıklarsan **Why?** penceresi açılır.
5. “Bana sadece komedi öner”, “All genres” ya da seçtiğin bir filmin adını yazarak sonuçları değiştir.

Model kapalıysa açık bir hata mesajı görürsün; **Try that step again** seçimlerini kaybetmeden yeniden dener. İstek sınırına takılırsan bir dakika bekle.

Siteyi başka bilgisayarlara açacaksan `.env` içinde `REQUIRE_API_KEY=true` yap. O zaman arayüz **APP_API_KEY** değerini ister. Bu değeri ekran görüntüsüne ya da Git'e ekleme.

## 4. Sunum ve kalite kontrolleri

| Komut | Ne yapar? |
|---|---|
| `make lint` | Pylint denetimi (en az 9.5 puan) |
| `make test` | Frontend testleri ve gerçek Neo4j ile Python testleri, coverage dahil |
| `make demo` | Çalışan servislere canlı HTTP kontrolleri |
| `make assistant-eval` | Gerçek modelle sohbet akışını sınar |
| `make llm-eval` | Query lab'in 40 vakalık güvenlik ve doğruluk değerlendirmesi |

Ayrıntılar: [gösterim akışı](demo-runbook.md), [asistan mimarisi](film-assistant.md), [ölçülen sonuçlar](results.md), `demo.ipynb` ve `proje_guide.pdf`.

`make stop` servisleri durdurur ama verileri korur. Repo ve konteyner imajı özeldir (private). Ücretli bir LLM ya da bulut Neo4j hesabı gerekmez.
