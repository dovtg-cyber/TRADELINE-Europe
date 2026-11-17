# 03. Реестр источников, загрузка, версии, Time Machine

Реестр: `legal-api/sources/registry.json` (валидатор: `app/registry.py`, тесты `tests/test_registry.py`). Проверено 16.11.2026.

## 1. Что проверено в этом запуске
| Источник | Что подтверждено | Ссылка |
|---|---|---|
| Sejm ELI API (Dziennik Ustaw, Monitor Polski) | Поля `ELI`, `announcementDate`, `entryIntoForce`, `inForce`, `status`, `texts[type H/O/I/T]`, `references` («Akty zmieniające», «Akty zmienione», «Akty uznane za uchylone», «Odesłania»); тексты `/text.html`, `/text.pdf`; схема ELI `eli.gov.pl/eli/{dziennik}/{rok}/{pozycja}/{ogl\|tj\|uj}/pol/{pdf\|html}` | https://api.sejm.gov.pl/API_pl.html · https://api.sejm.gov.pl/eli_pl.html |
| CELLAR (EUR-Lex) | SPARQL: `https://publications.europa.eu/webapi/rdf/sparql` (GET/POST); REST по URI ресурсов с согласованием содержимого; RSS уведомлений о загрузке: `http://publications.europa.eu/webapi/notification/ingestion` | описание Publications Office (презентация) и примеры запросов, найдены поиском |
| Реальный акт для проверки модели дат | Council Regulation (EU) 2026/382 от 11.02.2026, OJ L 18.2.2026, ELI http://data.europa.eu/eli/reg/2026/382/oj, ст. 2: €3 за единицу при партии до €150 с 1.07.2026 по 1.07.2028 | https://eur-lex.europa.eu/eli/reg/2026/382/oj · https://taxation-customs.ec.europa.eu/Customs/eu-Customs-Reform_en |
| TARIC | Правовая база Reg. (EEC) 2658/87; сырые данные «бесплатно в Excel»; нет НДС и акцизов; группа CIRCABC «TARIC and Quota Data & Information» | https://taxation-customs.ec.europa.eu/online-services/online-services-and-databases-customs/eu-customs-tariff-taric_en |

**Не подтверждено, остаётся в реестре как `to_verify` / «to_confirm»:** условия повторного использования EUR-Lex и Sejm ELI, лимиты запросов, формулировка «консолидированный текст не имеет юридической силы» (в EUR-Lex), условия доступа к TARIC raw (старая страница CIRCABC требует EU Login), правила robots для страниц консультации TARIC (сообщение стороннего инструмента, напрямую не проверено), польские порталы Минфина и таможни (KAS), свойства CDM для даты вступления в силу и конца действия. До проверки такие источники не используются как доказательства (валидатор это запрещает).

## 2. Уровни источников
1. Первичные официальные: Official Journal (EUR-Lex), Dziennik Ustaw / Monitor Polski, TARIC как инструмент.
2. Официальные разъяснения (Еврокомиссия, Минфин): показываются как «разъяснение», не как норма.
3. Вторичные (блоги, консалтинг, новости): только для поиска первоисточника; `evidence_allowed=false`, валидатор запрещает обратное. Пример: в поиске два вторичных источника по Reg. 2026/382 дали разные номера актов и даты; решающим был текст EUR-Lex.

## 3. Загрузка (ingestion)
1. Cron раз в сутки: список изменений (Sejm ELI `changeDate`, CELLAR RSS), для каждой записи `ingestion_run`.
2. Скачать оригинал (HTML/XML/PDF), сохранить в хранилище, посчитать SHA-256, записать `retrieved_on`, URL.
3. Разобрать метаданные (даты, связи) и текст по статьям (`article_chunk`).
4. Если текст изменился: НЕ перезаписывать, создать новую версию, закрыть предыдущую (`version_to`), создать `change_event`.
5. PDF без текстового слоя: не индексировать, пометить для ручной обработки (`NoTextLayer`).
6. Любая ошибка в `ingestion_run.errors`; частичная загрузка не публикуется.

## 4. Provenance
Для каждой версии: `source_id`, `url`, `retrieved_on`, `sha256` оригинала и текста, `ingestion_run`. Для каждого ответа: `research_evidence` (какая версия, статья, цитата, результат проверки) и хэш входа модели. Это позволяет доказать, на какой версии построен ответ.

## 5. Пять дат и Legal Time Machine (`app/timemachine.py`)
Даты: принятия, публикации, вступления в силу, начала применения, окончания применения. Хранятся раздельно; неизвестная дата не подставляется, а даёт предупреждение.

Состояния: `not_yet_published` · `published_not_in_force` · `in_force_not_applicable` · `applicable` · `applicable_boundary_check` · `ceased` · `unknown`. Опираться на обязательное утверждение можно только в состоянии `applicable`.

Рабочий пример (тест `test_five_dates_kept_apart`), Reg. (EU) 2026/382: принят 11.02.2026; опубликован 18.02.2026; вступление в силу по правилу «на двадцатый день после публикации» = 10.03.2026 (**вычислено, сверить с датой в EUR-Lex**); применяется с 01.07.2026; «until 1 July 2028». Результат: 20.02.2026 опубликован, но не в силе; 15.03.2026 в силе, но не применяется; 01.08.2026 применяется; 01.07.2028 граница, нужна проверка человеком (включительно ли «until»); 02.07.2028 прекратил применяться.

## 6. Мониторинг изменений
`change_event` порождается при новой версии, новой связи «изменяет/отменяет» или смене статуса. Дальше: список клиентов, чьи товары, страны или акты затронуты (по их рабочему пространству), и уведомление. Пример реального изменения для проверки в бою: переход с 01.07.2026 к €3 за единицу и обязательные идентификаторы товара (PID) с 01.11.2026 (по данным страницы Еврокомиссии).
