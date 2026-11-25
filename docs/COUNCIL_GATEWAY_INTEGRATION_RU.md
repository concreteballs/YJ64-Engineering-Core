# Интеграция Council Gateway с консилиумом YJ-64

> **Граница ответственности:** здесь описан только клиент Gateway/result adapter и интеграция с parent engineering task в Engineering Core. Motocicl владеет автономным циклом, долговечной orchestration и cycle-side caller. Приложение YJ-64 владеет собственным движком консилиума.
>
> [Контракт интеграции со стороны цикла](https://github.com/concreteballs/Motocicl/blob/main/docs/ENGINEERING_CORE_COUNCIL_GATEWAY_INTEGRATION_RU.md).


## Назначение и граница ответственности

Council Gateway — клиент защищённого внешнего API и слой долговечной передачи результатов в YJ64 Engineering Core.

Приложение YJ-64 остаётся единственным владельцем моделей, маршрутизатора моделей, участников, внутренних сообщений, протоколов Consensus и Critique, раундов, голосования и состояния сессии.

Gateway не создаёт второй консилиум, не вызывает API отдельных моделей и не воспроизводит внутреннюю логику обсуждения.

## Что фактически найдено в приложении

Проверен репозиторий concreteballs/yj64-clean-bial2modFun5, ветка main.

- message_distributor.py распределяет запросы между участниками.
- llm_api.py централизует обращения к провайдерам моделей.
- main.py содержит последовательные раунды общего чата, отдельный цикл группового диалога, prompt-based Critique mode и пользовательские кнопки управления.
- chat_workspace.py сохраняет историю чатов в локальных JSON-файлах приложения.
- services/internal_monitor.py использует Android Content Provider IPC для диагностических отчётов. Это не внешний API консилиума.

В проверенном коде пока не обнаружены:
- отдельный формальный движок принятия Consensus-решения;
- структурированный конечный автомат Consensus/Critique/Voting;
- серверный HTTP API для внешнего агента;
- машинная идентичность внешнего агента и проверка его полномочий;
- долговечные серверные записи удалённых council request/session;
- API статуса, результата и отмены сессии.

Флаг consensus_reached и текстовый маркер [CONSENSUS: APPROVE/OBJECT] сами по себе не доказывают наличие полноценного протокола консенсуса. В плане приложения описана будущая реализация Consensus/Critique/Voting/Decision Integrity, но документация не является доказательством реализации.

**Следствие:** Gateway можно реализовать на стороне Engineering Core, но живое сквозное взаимодействие пока невозможно подтвердить. Приложение YJ-64 должно предоставить внешний API и подключить его к своему реальному механизму многомодельного обсуждения. Обычный последовательный чат нельзя выдавать за завершённый консенсус.

## Контракт yj64.council-api.v1

Каноническая схема: [Motocicl — schemas/council-api-v1.schema.json](https://github.com/concreteballs/Motocicl/blob/main/schemas/council-api-v1.schema.json). Локальный `schemas/council-api-v1.schema.json` в Engineering Core сохранён только как compatibility snapshot; при изменении протокола сначала обновляется каноническая схема Motocicl, затем синхронизируется этот файл.

Предлагаемые маршруты, используемые клиентом:

| Операция | Метод и маршрут |
|---|---|
| Отправить запрос | POST /api/v1/external-agents/council/requests |
| Получить статус | GET /api/v1/external-agents/council/requests/{request_id} |
| Получить результат | GET /api/v1/external-agents/council/requests/{request_id}/result |
| Отменить | POST /api/v1/external-agents/council/requests/{request_id}/cancel |

Это конкретное предложение контракта, а не утверждение, что маршруты уже существуют в приложении. Их необходимо реализовать на стороне YJ-64 или явно согласовать отображение маршрутов до запуска production-интеграции.

Все операции используют отдельный Bearer token машинной идентичности. Приложение должно проверять владельца запроса и scope для каждой операции. Токен хранится только в серверных secrets.

### Режимы и статусы

Режимы:
- consensus — анализ, содержательная критика аргументов и доказательств, попытка согласовать вывод без искусственного единогласия;
- critique — независимая проверка предложения или решения.

Голосование задаётся отдельно и по умолчанию выключено. В запросе явно передаются voting.enabled и voting.weighted. Если голосование включено, наружу возвращается только агрегированный итог; индивидуальные бюллетени и приватные рейтинги запрещены. Лимиты также задают политику ранней остановки при содержательной сходимости.

Статусы выполнения: accepted, running, completed, blocked, failed, cancelled.

Содержательные исходы завершённой дискуссии:
consensus, qualified_consensus, unresolved_disagreement, insufficient_evidence.

Статус выполнения нельзя смешивать с содержательным исходом. Ошибка, блокировка, тайм-аут или нехватка данных не могут превращаться в консенсус.

### Структура результата

Результат включает:
- идентификаторы request/session и версию протокола;
- краткое резюме и содержательный исход;
- атомарные claims с классификацией fact, inference, hypothesis или test_result;
- позиции участников и существенные возражения;
- evidence с типом, описанием и проверяемой ссылкой;
- нерешённые вопросы, предположения и ограничения;
- число раундов и причину завершения;
- результаты тестов и симуляций, если они проводились;
- только агрегированный итог голосования, если оно было включено.

Скрытые рейтинги, приватные сообщения, секретные индивидуальные бюллетени, внутренние промпты и ключи провайдеров наружу не передаются.

## Реализация в Engineering Core

- automation/browser_agent_bridge.py — оставленный в Engineering Core совместимый helper для формирования/проверки envelope `yj64.browser-agent-envelope.v1`, используемый Gateway adapter. Общий browser-agent feedback transport и cycle-side bridge принадлежат Motocicl; helper здесь не означает владение циклом.
- automation/council_gateway.py — HTTPS-клиент, машинная аутентификация, лимиты, проверка протокола, идентификаторов и структуры результата.
- automation/council_tasks.py — постановка запроса, асинхронный polling, checkpoints, сохранение результата, handoff и load_council_result_artifact(...) для агента-потребителя.
- automation/council_decision_policy.py — повторный расчёт Decision Integrity и построение ограниченного плана проверок по фиксированным enum-кодам. Текст Council не переносится в действия; результат всегда `advisory_only`, `execution_allowed=false`, без изменения permissions и без исполняемых действий.
- scripts/run_council_gateway_worker.py — одношаговый worker.
- .github/workflows/scheduled-council-gateway-worker.yml — запуск worker по расписанию.
- schemas/council-api-v1.schema.json — JSON Schema контракта.

Используется существующая PostgreSQL Task Queue, существующие durable checkpoints и private Supabase artifact storage. Новая очередь не создаётся.

Новые типы задач:
- submit_council_request;
- poll_council_request;
- council_result_ready — результатный handoff, который обрабатывает зарегистрированный handler handle_council_result_ready в Council Gateway worker.

Жизненный цикл:
1. GitHub-агент отправляет council_request в существующем формате yj64.browser-agent-envelope.v1. Функция enqueue_council_request_from_envelope(...) проверяет область репозитория/ветки, срок действия, тип сообщения, idempotency key и хеш payload. Хеш подтверждает целостность, но не подлинность отправителя: принимающая граница всё равно должна аутентифицировать агента и проверить его полномочия.
2. Внутренний инженерный workflow может вызывать enqueue_council_request(...) напрямую, если уже имеет авторизованный контекст задачи.
3. Submit worker отправляет один аутентифицированный запрос и получает request_id и session_id.
4. Идентификаторы сохраняются в checkpoint, создаётся poll task, текущий worker освобождается.
5. Каждый poll worker делает один запрос статуса. Если сессия ещё выполняется, он создаёт следующее поколение poll task и завершает текущую задачу.
6. После завершения результат проверяется и сохраняется как immutable artifact в существующем private Supabase Storage. Задача council_result_ready содержит ссылку на artifact и envelope council_result, связанный с исходной задачей.
7. Result-ready handler проверяет envelope, artifact, request/session IDs, parent identity и структуру результата. Проверенные summary, claims, evidence, dissent, unresolved_questions, assumptions и limitations сохраняются в checkpoint как недоверенные аналитические данные.
8. Если передан числовой parent_task_id без внешнего parent_task_ref, та же транзакция PostgreSQL проверяет, что родительская запись находится в состоянии waiting, а последний checkpoint ожидает именно этот Council request. Затем создаётся идемпотентное resume-событие, добавляется hash-linked checkpoint родителя со ссылкой и digest результата, и та же родительская задача возвращается в pending. Повторная доставка не создаёт второе событие и не запускает повторную постановку задачи.
9. До обращения к Gateway родительский handler обязан иметь непустой проверенный checkpoint с исходной целью и контекстом. Если checkpoint отсутствует или повреждён, запрос блокируется до внешнего submit и постановки poll task. При ожидании сохраняются исходное состояние (включая контекст, решения и историю), budgets, approvals и artifact refs; в checkpoint также записывается SHA-256 исходного payload родительской queue-записи. Повторный запуск после сбоя suspension повторно освобождает ту же задачу без повторного submit и без создания нового poll поколения.
10. После handoff существующий handler родительской задачи, а не новый цикл, должен вызвать TaskContext.load_council_resume(), сформировать собственное решение и записать факт потребления результата через TaskContext.checkpoint_council_resume_consumed(...). При загрузке проверяются положительный resume_event_id, отдельный result_task_id, request/session identity, opaque artifact ref, SHA-256 и маркер недоверенных данных. Helper сохраняет снимок исходного состояния родителя, budgets, approvals и исходные artifact refs; checkpoint нельзя использовать для повышения разрешений/бюджетов или удаления/перестановки исходных артефактов.

   Потребление результата не означает завершение родительской задачи. После approved continuation handler существующий владелец цикла обязан вызвать отдельный доверенный `parent_cycle_handler`, который продолжает исходную инженерную задачу с её checkpoint, целью, контекстом и историей. Для записи прогресса используется `TaskContext.checkpoint_council_parent_progress(...)`: он разрешает только смену stage, append-only добавление записей в существующие `history` и `decision_log`, а также append-only добавление artifact refs; исходные записи, context, budgets и approvals сохраняются. Возврат `completed` или `suspended` допускается только после нового checkpoint с продвижением стадии. Если `parent_cycle_handler` отсутствует либо не сохранил прогресс, задача блокируется, а не помечается завершённой.

   После перезапуска worker уже потреблённый Council resume распознаётся по hash-verified checkpoint. Повторно не запускаются Council submit, Decision/Executor continuation и уже потреблённая операция; вызывается только `parent_cycle_handler` для продолжения с последнего сохранённого stage. При завершённом Council result `handle_council_request_in_parent_task(...)` передаёт continuation handler два отдельных объекта: `decision_assessment` (типизированные Claim/Evidence/Decision records) и `decision_policy` (фиксированная рекомендация `resolve_conflict`, `collect_independent_evidence`, `human_review` или `independent_domain_validation`). Policy заново рассчитывает Decision Integrity и не использует свободный текст для выбора действия. Родительский цикл обязан сопоставлять recommendation с собственным доверенным domain handler; это не разрешение на запуск команд.
11. Если передан только внешний parent_task_ref, Engineering Core проверяет и сохраняет ссылку, но не пытается угадать числовой ID очереди и не переотправляет постороннюю задачу. Для такого родителя необходим cycle-side consumer с отдельным согласованным контрактом чтения/диспетчеризации.

Результат консилиума остаётся недоверенными данными. Он не передаётся напрямую исполнителю команд и не может выдавать разрешения или approvals.

## Настройка GitHub Actions secrets

Необходимы:
- YJ64_DATABASE_URL;
- YJ64_COUNCIL_API_URL — HTTPS origin внешнего API YJ-64;
- YJ64_COUNCIL_AGENT_TOKEN — отдельный машинный токен с минимальными полномочиями;
- SUPABASE_URL;
- SUPABASE_SERVICE_ROLE_KEY — только серверный ключ для private artifact storage.

Необязательные GitHub repository variables:
- YJ64_COUNCIL_AGENT_ID (по умолчанию yj64-engineering-core);
- YJ64_COUNCIL_SUBMIT_PATH, YJ64_COUNCIL_STATUS_PATH, YJ64_COUNCIL_RESULT_PATH и YJ64_COUNCIL_CANCEL_PATH — для отображения предварительных маршрутов на окончательные пути, согласованные с разработчиком приложения YJ-64.

Polling выполняется каждые пять минут, максимум тремя одношаговыми worker одновременно. По умолчанию разрешено 288 проверок; жёсткий максимум — 2 016 проверок (семь дней). Для повторной доставки результата используются стабильные ID и временные метки envelope. Worker не удерживается на ожидании дискуссии.

## Что ещё необходимо для настоящей интеграции

На стороне приложения YJ-64 необходимо:
1. реализовать внешний API и машинную аутентификацию;
2. подключить API к существующему внутреннему механизму многомодельного диалога;
3. реализовать и сохранять реальный Consensus/Critique lifecycle и структурированный результат;
4. обеспечить idempotency, восстановление после рестарта, отмену, лимиты и аудит;
5. пройти сквозные тесты на настоящем приложении, а не только на mock API.

Motocicl остаётся владельцем автономного инженерного цикла и его dispatcher. Engineering Core предоставляет долговечный Gateway adapter, строгий контракт возобновления числовой parent-задачи и advisory decision policy, но не регистрирует и не запускает parent handler Motocicl.

Read-only проверка Motocicl `main` на 22 ноября 2026 года выявила конкретный cycle-side блокер: `scripts/run_motocicl_worker.py` регистрирует только `prepare_ci_fix` и условно `generate_ci_patch`; инженерный parent handler и `council_result_ready` consumer там не зарегистрированы. Текущий Motocicl `TaskContext` не передаёт `task_payload` и не предоставляет `checkpoint_council_resume_consumed(...)`; его `WorkerRunner` проверяет лишь факт выхода checkpoint из `council_resume_ready`, а не полный Core-контракт сохранения контекста и permissions. Этот репозиторий не изменялся. Для завершения Pass 1 нужен отдельный cycle-side адаптер/регистрация в Motocicl с согласованным переносом строгого resume-контракта; без этого Core не может честно объявить продолжение подключённым к существующему циклу.

Миграция `0021_council_parent_resume.sql` находится в Engineering Core, но live database не изменялась. Ранее worker получил `UndefinedTable` для `yj64_task_resume_events`; до отдельного разрешения на миграцию live E2E остаётся заблокирован.

Cycle-side worker также должен потреблять внешний `parent_task_ref` через отдельно согласованный контракт чтения и диспетчеризации. Эта часть не реализована и не проверена изменениями в данном репозитории; поэтому автоматическое продолжение всего цикла и live E2E пока не подтверждены.

До готовности API и этого consumer в Engineering Core есть клиент и асинхронная оркестрация, но реальное сквозное подключение к консилиуму не считается завершённым.
