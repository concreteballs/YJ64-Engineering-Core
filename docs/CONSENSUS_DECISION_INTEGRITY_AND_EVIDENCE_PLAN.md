# Consensus, Decision Integrity and Evidence-Based Engineering — Implementation Plan

Status: Planned architecture, approved for staged implementation
Repository: concreteballs/YJ64-Engineering-Core
Branch: main

## Scope and boundaries
This plan covers reusable consensus, voting, competence evaluation, evidence integrity and practical-validation contracts for the Engineering Core. The autonomous GitHub cycle is responsible only for executing bounded tasks, observing CI/runtime evidence, communicating with the browser agent when information is missing, and continuing or stopping safely. Do not duplicate the application's supervisory module: round limits, participant instruction injection, repetition detection and session stop enforcement remain app-level responsibilities.

Before each stage, audit existing Engineering Core math, physics, chemistry, solver, evidence, testing, diagnostics and persistence components. Reuse directly or via adapters; no duplicate engines.

## 1. Consensus and Critique protocol
- Configurable round ceiling, mandatory critical review in autonomous deliberation, early stop when stable consensus is supported.
- Criticism must address actual claims/arguments, never manufacture disagreement.
- Consensus is not required. Outcomes may be: supported consensus, qualified consensus, unresolved disagreement, insufficient evidence, or invalid/incomplete session.
- Never pressure a model to change position just to finish.
- Consensus is not truth. Preserve minority objections and supporting evidence.
- Consensus and Critique are separate modes: consensus evaluates proposed decisions; critique examines an object and converges on a critique protocol, without falsely implying the object itself is disproven.
- No automatic restart of a finished session. A user/authorized controller may start a new session.

## 2. Voting Engine
- Extract/normalize atomic claims from the discussion and accept user-added ballot questions.
- Give all participants the same ballot statements; independent, private votes: FOR, AGAINST, ABSTAIN, CONDITIONAL.
- Lock votes before aggregate results are shown; prevent leakage through interim counts, ordering, coordinator prompts, rankings or exposed metadata.
- Calculate simple majority and competence-weighted results separately. Show disagreements and reliability/uncertainty.
- If voting is enabled, conduct it after consensus or after round exhaustion/unresolved disagreement. If disabled, emit the deliberation protocol without ballots.
- Majority does not establish correctness.

## 3. Competence model and private ratings
Ratings are private system metadata; models must not see ratings, numeric scores, ranking comparisons, or hints designed to influence voting. Do not include rating data in prompts, shared chat, public result text to models, or ordering that leaks ranking.

Maintain separate, domain-specific and global metrics:
- independently verified task correctness;
- practical/experiment/simulation/test outcome agreement;
- majority alignment (descriptive, not truth);
- critique quality (validated actionable defects found, false-positive burden, severity);
- prediction calibration;
- abstention and conditional-vote quality where evidence supports scoring.

A minority vote that matches a verified result must be credited for correctness and evidence; a majority-aligned incorrect vote must be penalized by error severity. Do not reward contrarianism: disagreement receives no bonus by itself; wrong predictions/votes receive a penalty; verified correctness is credited regardless of majority. A model should not know its rating exists or be able to optimize behavior against it.

Ratings must include sample count, confidence/uncertainty, task difficulty, verification independence, recency/decay and topic specificity. Avoid large score shifts from tiny samples. No majority-derived label may be treated as ground truth. Provide a private, scoped API for agents to receive only the domain-relevant probabilistic reliability estimates, not unnecessary cross-domain profile data.

The rating's purpose is decision support: estimate likelihoods with uncertainty and guide where to investigate or which model is useful for a domain. It is not a truth oracle and must never be the sole selection or decision mechanism.

## 4. Decision Integrity Engine
An algorithmic checker, separate from the LLM deliberation, validates evidence relationships and machine-checkable claims. It is context-aware and does not equate formal presence with validity.
- Claims are atomized and traceable to speaker/source.
- Evidence contains exact repo path/line or symbol, commit/version/hash, test or calculation identifiers, and scope/assumptions.
- Verify quote existence and source version, citation-to-claim link, tests targeting the claimed behavior, type/contracts, dimensional/unit consistency, formal proof obligations when available, boundary conditions and machine-checkable constraints.
- Track repetition/no-progress, contradictions, retries and limits, plus evidence completeness in the final record.
- Preserve speaker attribution; never invent or paraphrase a participant's position as a claim they did not make.
- Abstract/non-code claims require a minimal reproducible example, model, pseudocode or explicit testable sequence when feasible.
- Claim statuses: verified, partially verified, hypothesis, unverified, refuted; preserve counterevidence and scope.

## 5. Evidence hierarchy and virtual validation
Evidence is typed, scoped and not treated as a universal ranking:
1. Physical experiment (if feasible, suitable, ethical/safe, and quality-controlled).
2. Independent empirical data/observation relevant to the claim.
3. Validated virtual/model result with applicability, assumptions, solver and uncertainty documented.
4. Formal proof (strong only for the propositions/assumptions actually covered).
5. Deterministic tests, contracts, dimensional/type checks and numerical calculations.
6. Model arguments, consensus and votes.
Ordering is context-dependent: a proof can outrank an experiment for a formal proposition, and an experiment may be weaker than a well-validated model if precision/measurement limitations are material. The engine must record the evidence's scope and limitations rather than blindly use a fixed ranking.

For most engineering problems, simulation/calculation is the practical final validation stage when physical experimentation is unavailable or unjustified. Do not label simulation as experimentally verified. Record "physical experiment not conducted"; update the result only when relevant new experimental data or observations arrive, even indirectly. Never assert that simulation confirms physical reality without model-validation evidence.

## 6. Practical feedback and outcome review
After a recommendation, the authorized agent may test feasibility, implement an approved bounded change, run deterministic tests, calculations, simulations, or experiments. Results return to deliberation as evidence. Compare initial predictions, votes and confidence with outcome evidence; update rating statistics only after outcome labels meet the independent-verification requirements. Record model validity, solver validity and result validity separately.

## 7. Virtual experiment workflow
For physical, chemical or multidisciplinary questions:
1. state hypothesis and variables;
2. specify parameters, assumptions, conditions and constraints;
3. select an existing model/solver or adapter;
4. check dimensions, boundaries and applicability;
5. select solver and version;
6. run bounded simulation/test and sensitivity/uncertainty analysis;
7. return evidence and limitations to participants;
8. allow bounded position/vote revision;
9. record provenance and experiment status.
Use existing physics, math, chemistry and solver facilities. No new simulation engine until audit identifies a capability gap.

## 8. Implementation feasibility / negative result protocol
If the agent cannot implement a consensus recommendation: preserve exact recommendation, identify current limitation, provide file/contract/calculation/log evidence, check alternatives, bound retries, prevent identical retry loops, and record unresolved/blocked status. Do not generalize an environment limitation into universal impossibility.

## 9. Competence test bench
Idle-time testing is bounded by task, token, cost, time and resource ceilings. Include independently scored domain tests, blind voting, critique validation, calibration, deterministic calculations and virtual experiments. Keep a held-out control set out of rating updates. Store task provenance, difficulty, labels and validation independence; don't run indefinitely or spend paid quotas without explicit budget.

## 10. Agent-facing rating interface
Expose only scoped domain reliability estimates, uncertainty, evidence counts, and rating version to authorized agents. Treat values as hints, not authority. Never reveal private ballots or ratings to participant models.

## 11. Session evidence record
Persist task/session IDs, model/version identifiers, round count, mode, atomic claims, critique, revisions, secret ballots in protected storage, aggregates, simple and weighted vote, uncertainty/sample reliability, predictions, calculation/test/simulation/experiment evidence, source commit/path references, consensus or dissent outcome, user decision and limitations. Models receive only the session-visible content, not ratings or private ballot records.

## 12. Staged implementation and acceptance
1. Audit reusable components and APIs; map each requirement to existing code or a gap.
2. Implement shared Claim/Evidence/Decision records and serialization.
3. Implement bounded Consensus/Critique protocol and termination outcomes.
4. Implement private independent ballots, aggregation and leakage tests.
5. Implement scoped ratings with uncertainty, sample-size guards, minority-correct credit, anti-contrarian incentive checks and held-out validation.
6. Implement algorithmic Decision Integrity checks and provenance.
7. Integrate existing mathematical/formal/physics/chemistry tools via contracts.
8. Implement outcome feedback and calibration update workflow.
9. Add bounded idle benchmark/test bench.
10. Integrate authorized agent interfaces.
11. Validate false consensus, minority-correct, majority-wrong, insufficient evidence, untested simulation, source mismatch, ballot leakage, repeated/no-progress, context-limited impossibility, and session-budget exhaustion.

No stage may be marked complete without task-level acceptance tests and evidence. Implement small additive increments, preserve current interfaces, and update IMPLEMENTATION_STATUS.md only when code is actually delivered.
13. Междисциплинарные связи модулей и комплексная оценка безопасности инженерных решений

13.1. Цель и обоснование

Научные и инженерные дисциплины не существуют изолированно. Реальные процессы часто зависят от нескольких областей знания одновременно, причём взаимосвязи могут быть нелинейными, многоуровневыми и неочевидными заранее.

Инженерное решение, оптимальное с точки зрения прочности, массы, стоимости, энергопотребления или производительности, может оказаться непригодным для практического применения из-за химических, биологических, экологических или иных последствий, которые не были учтены при первоначальном проектировании.

Поэтому Engineering Core должен развиваться не как набор изолированных специализированных модулей, а как система, способная постепенно формировать, расширять и использовать междисциплинарные связи.

Мы делаем это для того, чтобы система могла обнаруживать последствия, которые невозможно увидеть, рассматривая задачу только с позиции одной дисциплины.

Например, разработка искусственной мышцы робота может одновременно требовать:

- инженерии — конструкция, прочность, ресурс, производимость;
- физики — силы, динамика, тепловые режимы, энергия;
- химии — состав материала, реакции, стабильность, токсичность;
- биологии — молекулярные механизмы, биосовместимость, микробный рост;
- математики — моделирование, оптимизация, анализ неопределённости;
- экологии — воздействие на окружающую среду, отходы и жизненный цикл.

Подобные связи должны обнаруживаться самой системой, а не зависеть исключительно от того, вспомнил ли пользователь или отдельная модель о необходимости привлечь другую область знаний.

13.2. Универсальная архитектура межмодульного взаимодействия

Необходимо заранее предусмотреть архитектуру, позволяющую модулям взаимодействовать различными способами.

Не следует ограничиваться жёстко заданными связями между двумя конкретными модулями. Архитектура должна поддерживать развитие новых связей, подключение новых дисциплин и более сложные цепочки совместного анализа без необходимости переписывать ядро.

Предусмотреть следующие типы взаимодействия:

1. Запрос консультации — один модуль запрашивает анализ у другого специализированного модуля.
2. Передача доказательств и данных — модули передают друг другу расчёты, результаты исследований, наблюдения и проверенные факты.
3. Совместный анализ — несколько модулей одновременно исследуют одну задачу, каждый со своей точки зрения.
4. Событийное взаимодействие — результат одного модуля автоматически запускает дополнительную проверку в другом.
5. Цепочки анализа — результат одной дисциплины становится исходными данными для нескольких других, после чего результаты возвращаются в общий анализ.
6. Взаимная проверка — один модуль проверяет предположения, ограничения и выводы другого.
7. Обнаружение конфликтов — система фиксирует несовместимые выводы, различия в предположениях и неопределённости.
8. Динамическое подключение дисциплин — возможность привлекать дополнительные модули в процессе решения задачи, если обнаружены новые факторы.

Связи должны быть постепенно развиваемыми, расширяемыми, версионируемыми и проверяемыми.

Каждый запрос и ответ между модулями должен иметь идентификатор задачи, контекст, исходные данные, версию объекта исследования, ограничения, статус, доказательства и результат.

Модули не должны автоматически соглашаться друг с другом. Каждый сохраняет свою специализацию и право сообщить о противоречиях, недостаточности данных или невозможности сделать обоснованный вывод.

13.3. Автоматическое обнаружение необходимости междисциплинарного анализа

Engineering Core должен оценивать, какие области знания необходимы для решения конкретной задачи.

Например, при разработке нового материала система должна учитывать не только его механические характеристики, но и то, может ли он:

- вступать в опасные реакции;
- выделять вредные вещества при нагреве, износе или старении;
- создавать условия для накопления влаги и микробного роста;
- представлять опасность при контакте с человеком или животным;
- загрязнять окружающую среду;
- терять свойства в реальных условиях эксплуатации.

Если обнаруживается фактор, выходящий за пределы компетенции текущего модуля, должен запускаться соответствующий межмодульный запрос.

Это должно работать и в обратном направлении: химический, биологический или физический модуль, обнаруживший проблему, может инициировать пересмотр инженерного решения.

13.4. Обязательная химическая оценка инженерных материалов

При разработке материалов, покрытий, жидкостей, полимеров, композитов и других объектов, для которых химические свойства имеют значение, инженерный модуль должен при необходимости подключать химический модуль.

Оценка должна учитывать:

- состав и химические свойства материала;
- опасные свойства и известные токсикологические данные;
- реактивность и несовместимость с другими веществами;
- коррозию и разрушение;
- продукты разложения, старения и износа;
- возможные выделения в окружающую среду;
- пути воздействия на организм;
- условия производства, эксплуатации, ремонта и утилизации.

Цель — выявлять потенциальные опасности до того, как материал будет рекомендован к практическому применению.

13.5. Обязательная биологическая оценка

Биологический модуль должен подключаться при наличии потенциального биологического воздействия, биосовместимости, загрязнения, микробного роста или взаимодействия материала с живыми организмами.

Оценка должна учитывать:

- молекулярную структуру веществ и материалов, когда она имеет значение для биологической функции;
- свойства поверхности и вероятность удержания загрязнений;
- наличие влаги, застойных зон и подходящих температурных условий;
- возможность образования биоплёнок;
- возможность очистки, дезинфекции и обслуживания;
- потенциальные пути воздействия на человека, животных и окружающую среду;
- доступные доказательства и неопределённости.

Биологический модуль должен не просто выдать отметку о риске, но и объяснить механизм его возникновения.

Например, при оценке материала он должен уметь объяснить, почему определённые молекулярные компоненты, свойства поверхности, доступность воды или другие факторы имеют значение для рассматриваемого биологического процесса.

При этом необходимо строго различать теоретическую возможность, благоприятные условия, подтверждённый рост конкретного микроорганизма и доказанный риск заболевания. Наличие определённых веществ само по себе не доказывает присутствие патогена или возникновение инфекции.

13.6. Молекулярные объяснения, формулы и механизмы

При необходимости биологический и химический модули должны объяснять устройство молекул и функциональность их компонентов на соответствующем уровне детализации.

Объяснение может включать:

- молекулярную структуру;
- функциональные группы;
- химические связи;
- взаимодействие молекул;
- роль отдельных компонентов в рассматриваемом процессе;
- реакционные механизмы;
- физико-химические условия, влияющие на процесс.

Где это полезно, необходимо использовать формулы, уравнения, обозначения реакций, количественные модели и расчёты.

При использовании формул обязательно:

- определять обозначения и переменные;
- указывать единицы измерения;
- обозначать принятые допущения;
- проверять размерность уравнений;
- объяснять, что именно формула позволяет установить;
- обозначать ограничения применимости;
- отделять расчётный результат от экспериментально подтверждённого.

Формулы не должны использоваться исключительно для придания ответу научного вида. Они должны помогать понять механизм, проверить вывод и установить причинно-следственную связь.

13.7. Комплексная оценка безопасности

При необходимости Engineering Core должен проводить комплексную оценку потенциальных последствий:

- химических;
- биологических;
- физических;
- токсикологических;
- экологических;
- эксплуатационных;
- связанных с воздействием на человека и животных.

Проверка должна учитывать не только нормальную эксплуатацию, но и возможные сценарии повреждения, перегрева, износа, старения, загрязнения, ремонта, очистки и утилизации.

Если выявлен существенный риск, система должна иметь возможность:

- инициировать повторное проектирование;
- предложить более безопасную альтернативу;
- потребовать дополнительной проверки;
- обозначить необходимость независимой экспертизы;
- ограничить или заблокировать рекомендацию о практическом применении до разрешения существенной неопределённости.

13.8. Обязательное объяснение рисков пользователю

В итоговом инженерном ответе недостаточно перечислить опасные вещества, биологические факторы, числовые показатели или технические предупреждения.

Каждый обнаруженный существенный риск должен сопровождаться понятным объяснением:

1. Что обнаружено? — описание конкретной опасности.
2. Почему это возникает? — механизм возникновения, включая химические, физические или биологические причины.
3. При каких условиях? — обстоятельства, при которых риск становится существенным.
4. Кого или что это может затронуть? — людей, животных, оборудование или окружающую среду.
5. Каковы возможные последствия? — объяснение практическим языком.
6. Как это можно уменьшить или устранить? — варианты изменения конструкции, выбора материала, условий эксплуатации или обслуживания.
7. Насколько мы уверены? — источник, расчёт, эксперимент, моделирование и ограничения полученных данных.

Техническое объяснение с формулами и механизмами должно сопровождаться понятным человеку описанием последствий.

Система не должна создавать ложное ощущение безопасности только потому, что в проведённой проверке опасность не была обнаружена.

13.9. Статусы результатов проверки

Для оценки безопасности и междисциплинарного анализа предусмотреть понятные статусы:

- Проверено в заданных пределах, существенных проблем не выявлено.
- Риск обнаружен.
- Требуется устранение или снижение риска.
- Требуется дополнительное исследование или независимая экспертиза.
- Недостаточно данных.
- Не оценивалось.

Отсутствие обнаруженного риска не является гарантией абсолютной безопасности.

13.10. Постепенное развитие системы связей

На начальном этапе необходимо реализовать базовые межмодульные интерфейсы и несколько наиболее важных связей.

В дальнейшем система должна постепенно развивать сеть взаимодействий, добавляя новые виды связи, новые дисциплины, новые методы анализа и новые механизмы передачи доказательств.

При этом расширение должно происходить без хаотичного роста числа связей, дублирования функциональности или неконтролируемого запуска множества модулей.

Необходимо учитывать полезность связи, качество получаемых результатов, затраты ресурсов, повторяемость запросов и возможность возникновения циклов.

Междисциплинарное взаимодействие должно быть управляемым, ограниченным по ресурсам и прозрачным для аудита.

13.11. Критерии принятия реализации

Реализация считается соответствующей плану, если:

- Engineering Core способен обнаруживать необходимость привлечения других дисциплин.
- Межмодульная архитектура поддерживает различные типы взаимодействия и расширение.
- Новые модули и типы связи можно добавлять без переписывания основного механизма.
- Инженерное решение может быть автоматически направлено на химическую и биологическую оценку.
- Результаты модулей сохраняют источники, версии, ограничения и неопределённости.
- Выявленные риски могут инициировать пересмотр конструкции.
- Биологические и химические механизмы объясняются научно корректно, при необходимости с формулами и молекулярными структурами.
- Итоговый ответ содержит понятное объяснение практических последствий обнаруженных рисков.
- Необоснованное утверждение о безопасности невозможно сформировать только на основании отсутствия предупреждений.
- Межмодульные конфликты, ошибки, отсутствие ответов и недостаточность данных не скрываются.
- Архитектура допускает постепенное развитие сложной сети взаимосвязей между дисциплинами.

Главный принцип: мы создаём не набор отдельных интеллектуальных инструментов, а постепенно развивающуюся систему взаимосвязанных знаний, способную учитывать сложные последствия решений, выходящие за пределы одной научной или инженерной области.
