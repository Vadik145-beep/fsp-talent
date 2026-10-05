# Банк задач: Mobile

30 параметрических шаблонов специализации `mobile`. Код: `backend/app/testing/engine/bank/mobile/`
(по модулю на тему), тесты: `backend/tests/engine/test_bank_mobile_*.py`.
Механика шаблонов и IRT — в [`docs/testing/engine.md`](../engine.md).

Примеры из `bank_examples` (порядок колбэков Activity/Fragment и строка с ошибкой в Kotlin)
в эти 30 не входят, их механика не повторяется.

## Состав

Грейды: Стажёр 6, Junior 8, Middle 9, Senior 7. Девять тем, в каждой от 2 до 5 шаблонов.
Все семь форматов: `code_output` 10, `numeric` 7, `single_choice` 4, `find_bug_line` 3,
`multi_choice` 2, `ordering` 2, `short_text` 2.

`a` и `b` заданы экспертно (до калибровки по реальным ответам): `b` — в пределах ±0,4 от
центра грейда (Стажёр −1,5; Junior −0,5; Middle 0,5; Senior 1,5), с разбросом внутри грейда.

Как сверен ответ:
- **трансляция** — код задачи переводится в Python (или JS, SQL) и выполняется;
- **независимый расчёт** — тест разбирает текст задачи и считает ответ своей реализацией,
  не используя внутренние структуры генератора;
- **вручную** — ответ — данные из документации; тест проверяет согласованность
  (ключевые слова, канонический порядок), но не вычисляет ответ.

| id | тема | формат | грейд | a | b | что проверяет | как сверен ответ |
|---|---|---|---|---|---|---|---|
| `mobile.kotlin_null_safety` | kotlin | code_output | Стажёр | 1,2 | −1,4 | `?.`, `?:`, `let`, `isNullOrEmpty`, smart cast: что напечатает функция с nullable-параметрами | независимый расчёт по тексту кода + ручной пример |
| `mobile.kotlin_collections` | kotlin | code_output | Junior | 1,3 | −0,4 | цепочки `filter/map/fold/groupBy/associateBy/chunked/zipWithNext`: целочисленное деление, `..` включительно, «последний выигрывает» | независимый расчёт по тексту кода + ручной пример |
| `mobile.kotlin_data_class_equality` | kotlin | numeric | Junior | 1,2 | −0,6 | размер `mutableSetOf` с `data class` / обычным классом, `copy`, `remove` | трансляция в Python (`dataclass(frozen)` / сравнение по ссылке) + ручные примеры |
| `mobile.kotlin_scope_functions` | kotlin | code_output | Middle | 1,4 | 0,6 | что возвращают `let/run/with/apply/also/takeIf`, изменение списка внутри | независимый расчёт по тексту кода + ручной пример |
| `mobile.swift_optionals` | swift | short_text | Стажёр | 1,1 | −1,2 | `print(Optional)`, `??`, `if let`, `Int(String)` для строк с пробелом/знаком/точкой | независимый расчёт по тексту кода + ручные примеры |
| `mobile.swift_value_reference` | swift | code_output | Junior | 1,4 | −0,5 | `struct` копируется, `class` — общая ссылка; цепочки присваиваний и изменений | трансляция в Python (копия / ссылка) + ручные примеры |
| `mobile.swift_defer_order` | swift | ordering | Middle | 1,3 | 0,4 | порядок `defer` (LIFO, по областям `do`/`if`/`for`, `return` до `defer`) | трансляция в Python (`defer` → `try/finally`) + ручной пример |
| `mobile.swift_closure_capture` | swift | code_output | Senior | 1,5 | 1,3 | capture list `[x]` копирует значение/ссылку при создании; без него — текущее значение | трансляция в Python (аргумент по умолчанию / позднее связывание) + ручной пример |
| `mobile.swift_retain_cycle` | swift | find_bug_line | Senior | 1,4 | 1,2 | какая строка `viewDidLoad` создаёт цикл сильных ссылок (sink, Timer, UIAction, хранимое замыкание) | вручную + структурная проверка: в остальных строках `self` только через `[weak/unowned self]` или в нехранимых замыканиях |
| `mobile.coroutines_launch_order` | concurrency | code_output | Middle | 1,5 | 0,7 | порядок вывода `launch/async/delay/join/await` в `runBlocking` | трансляция в Python asyncio на цикле с виртуальным временем + пример из документации |
| `mobile.coroutines_cancellation` | concurrency | code_output | Senior | 1,6 | 1,8 | `cancel()` vs `cancelAndJoin()`, `finally`, suspend в `finally`, `NonCancellable`, `withTimeout(OrNull)` | трансляция в asyncio с эмуляцией отмены Kotlin + примеры из документации |
| `mobile.gcd_main_queue_order` | concurrency | code_output | Middle | 1,4 | 0,5 | `main.async` (FIFO, вложенные), `sync` на другой очереди, `asyncAfter` | трансляция в цикл событий (`call_soon` / `call_later`) + ручной пример |
| `mobile.gcd_deadlock` | concurrency | multi_choice | Senior | 1,3 | 1,6 | какие фрагменты дают дедлок: `main.sync` из main, вложенный `sync` на serial, семафор + `main.async` | независимая модель очередей + ручные примеры |
| `mobile.ios_lifecycle_order` | app_lifecycle | ordering | Junior | 1,1 | −0,8 | колбэки UIViewController при push/pop/модальном показе, состояния сцены и AppDelegate | вручную по документации UIKit; тест — канонический порядок |
| `mobile.android_launch_mode_stack` | app_lifecycle | numeric | Middle | 1,3 | 0,5 | сколько экземпляров в стеке задачи при `standard/singleTop/singleTask` и «Назад» | независимый расчёт по тексту + ручной пример |
| `mobile.android_config_change_counts` | app_lifecycle | numeric | Middle | 1,3 | 0,8 | сколько раз вызовутся `onCreate/onDestroy/init ViewModel/onCleared/onSaveInstanceState` при повороте, смене темы, Home, смерти процесса | независимый расчёт по тексту + ручной пример |
| `mobile.storage_choice` | data_storage | single_choice | Стажёр | 1,0 | −1,8 | где хранить токен, PIN, кэш картинок, черновики, большой каталог, секрет API (iOS/Android) | вручную; тест по ключевым словам |
| `mobile.room_query_result` | data_storage | code_output | Junior | 1,2 | −0,3 | что вернёт `@Query`: WHERE с AND/OR, NULL, BETWEEN, ORDER BY, LIMIT/OFFSET | трансляция: запрос выполняется в настоящем SQLite |
| `mobile.room_migration_bug` | data_storage | find_bug_line | Middle | 1,2 | 0,3 | ошибка миграции Room: не поднята версия, миграция не зарегистрирована, не те версии, NOT NULL без DEFAULT, nullable не совпадает, не та таблица | независимые правила проверки Room по тексту кода |
| `mobile.retry_backoff` | networking_offline | numeric | Junior | 1,0 | −0,7 | задержки `retry` с множителем, потолком и `toLong()` | трансляция в JS и выполнение в Node.js + ручной пример |
| `mobile.http_cache_revalidation` | networking_offline | numeric | Senior | 1,3 | 1,4 | HTTP-кэш OkHttp: `max-age`/`no-cache`, ETag, 304 обновляет свежесть | независимый расчёт по тексту + ручной пример |
| `mobile.bitmap_memory` | performance | numeric | Стажёр | 1,2 | −1,3 | память Bitmap: ширина × высота × байт на пиксель, `inSampleSize`, несколько картинок, МиБ | независимый расчёт по формулировке |
| `mobile.diffutil_updates` | performance | numeric | Middle | 1,2 | 0,2 | сколько элементов DiffUtil отметит вставленными/удалёнными/изменёнными при разных `areItemsTheSame/areContentsTheSame` | независимый расчёт (LCS по ключам) |
| `mobile.android_memory_leak` | performance | find_bug_line | Senior | 1,3 | 1,1 | какая строка удерживает Activity: синглтон с `this`, `GlobalScope`, `observeForever`, слушатель или `postDelayed` без снятия | независимые правила + вручную |
| `mobile.compose_lazy_keys` | performance | single_choice | Senior | 1,4 | 1,5 | у какого элемента окажется состояние `remember` в `LazyColumn` с `key` и без после удаления/вставки | независимый расчёт по тексту |
| `mobile.ios_navigation_stack` | navigation | code_output | Junior | 1,2 | −0,6 | стек `UINavigationController`: push/pop (корень не снимается), popTo, setViewControllers, remove | независимый расчёт по тексту кода |
| `mobile.nav_popupto_backstack` | navigation | single_choice | Middle | 1,3 | 0,4 | back stack Navigation Compose: `popUpTo` (`inclusive`), `launchSingleTop`, `popBackStack(route)` | независимый расчёт по тексту кода + ручной пример; дистракторы — модели с типичной ошибкой |
| `mobile.android_dangerous_permissions` | publishing_permissions | multi_choice | Стажёр | 1,1 | −1,6 | какие разрешения Android 13 требуют runtime-запроса (dangerous vs normal) | вручную по справочнику `Manifest.permission` |
| `mobile.android_runtime_permission_flow` | publishing_permissions | single_choice | Junior | 1,3 | −0,2 | что сделает `RequestPermission` после 0/1/2 отказов, после выдачи, ручного включения, переустановки | вручную по документации; тест-соответствие |
| `mobile.release_version_fields` | publishing_permissions | short_text | Стажёр | 0,9 | −1,9 | `versionCode/versionName/minSdk/targetSdk`, `CFBundleVersion/CFBundleShortVersionString` | вручную |

Итого: трансляция кода — 9 шаблонов, независимый расчёт по тексту — 15, только вручную (с тестом
согласованности) — 6.

## Покрытие тем по грейдам

| тема | Стажёр | Junior | Middle | Senior | всего |
|---|---|---|---|---|---|
| kotlin | 1 | 2 | 1 | — | 4 |
| swift | 1 | 1 | 1 | 2 | 5 |
| concurrency | — | — | 2 | 2 | 4 |
| app_lifecycle | — | 1 | 2 | — | 3 |
| data_storage | 1 | 1 | 1 | — | 3 |
| networking_offline | — | 1 | — | 1 | 2 |
| performance | 1 | — | 1 | 2 | 4 |
| navigation | — | 1 | 1 | — | 2 |
| publishing_permissions | 2 | 1 | — | — | 3 |
| **всего** | **6** | **8** | **9** | **7** | **30** |

## Параметризация

У каждого шаблона меняются числа, имена, данные, структура кода и порядок вариантов: от сотен
до тысяч разных вариантов. Общий тест банка проверяет на 150 seed не меньше 50 разных
вариантов и что ни один ключ (кроме `numeric` и `short_text`) не встречается больше чем
в половине из 200 seed. Номер строки в `find_bug_line` меняется (перемешанные строки,
разное число полей и комментариев), в `code_output` вывод зависит от данных.

Генераторы отбрасывают неинтересные варианты: например, в задаче про `struct`/`class` вывод
обязан различаться для двух моделей, в задаче про capture list — отличаться от «наивного»
позднего связывания, в launchMode — от «каждый запуск добавляет экземпляр».

## Как сверялись ответы

Рантаймов Kotlin, Swift и Android/iOS на машине нет. Поэтому:

1. **Трансляция и выполнение.**
   - Kotlin-корутины и главная очередь GCD — однопоточные циклы событий. Код переводится в
     Python asyncio и выполняется на цикле с виртуальным временем (часы прыгают к ближайшему
     таймеру). Соответствие: `launch/async` → задача (старт через FIFO-очередь, как
     диспетчер `runBlocking`), `delay` → `sleep`, `join/await` → `await` задачи (завершённая —
     без приостановки), `withTimeout(OrNull)` → `wait_for`, `main.async` → `call_soon`,
     `asyncAfter` → `call_later`, `sync` на другой очереди — прямой вызов. Отмена в asyncio
     одноразовая, а в Kotlin любой suspend-вызов отменённой корутины сразу бросает
     исключение, поэтому `delay` транслируется в обёртку с этой проверкой.
   - Swift `defer` → вложенные `try/finally`; capture list → аргумент лямбды по умолчанию;
     `struct` → копия при присваивании.
   - Kotlin `data class` → `dataclass(frozen=True)`, обычный класс → сравнение по ссылке.
   - Запросы Room выполняются в SQLite (Boolean → 0/1, null → NULL).
   - Задержки `retry` считает Node.js (`Math.trunc` = `toLong()` для положительных).
2. **Независимый расчёт.** Тест разбирает формулировку и код регулярными выражениями
   и считает ответ своей реализацией (стек задачи Android, back stack навигации,
   HTTP-кэш, LCS для DiffUtil, модель очередей для дедлоков, правила проверки Room).
3. **Эталонные примеры** в тестах — разобраны вручную по документации.

Источники (по ним проверена семантика): Kotlin docs — Null safety, Scope functions,
Collections, Data classes; kotlinx.coroutines guide — Coroutines basics, Cancellation and
timeouts (`cancelAndJoin`, `finally`, `NonCancellable`, `withTimeoutOrNull`); The Swift
Programming Language — Optionals, Structures and Classes, Closures (Capture Lists),
Automatic Reference Counting, `defer`; Apple Dispatch — `DispatchQueue.sync/async/asyncAfter`;
UIKit — UIViewController, UISceneDelegate, UIApplicationDelegate; Android — Activity lifecycle
(`onSaveInstanceState` после `onStop` с API 28), ViewModel overview, Tasks and the back stack
(launchMode), Request runtime permissions (с Android 11 два отказа = больше не спрашивать),
Permissions overview (protection level), Room migrations, Bitmap memory, DiffUtil/ListAdapter,
Navigation (popUpTo, launchSingleTop), Compose Lists (item keys); RFC 9111 (HTTP caching).

## Известные ограничения

- **Нет рантайма Kotlin/Swift/Android/iOS.** Код задач не компилировался. Синтаксис проверен
  вручную, генераторы собирают код из проверенных шаблонов строк. Возможны предупреждения
  компилятора (неиспользуемая переменная, `defer` в конце блока) — на ответ не влияют.
- **Модели, а не реальные платформы.** asyncio-трансляция повторяет модель однопоточного
  цикла событий; совпадение с kotlinx.coroutines 1.7 опирается на документацию и пример
  из неё. Особенно тонкое место — `job.cancel()` без `join`: строка после `cancel()`
  печатается раньше, чем `finally` отменённой корутины (возобновление идёт через очередь).
- **GCD:** порядок «все `main.async` раньше `asyncAfter`» верен при условии, что код
  выполняется мгновенно — это сказано в формулировке. В задаче про дедлоки вложенный `sync`
  на последовательной очереди и `main.sync` из главного потока на современных iOS чаще
  падают (libdispatch ловит ситуацию), чем зависают — формулировка явно считает оба исхода
  дедлоком. Вложенный `sync` на concurrent-очереди считается безопасным.
- **Жизненный цикл iOS:** взят порядок для одного контроллера и сцены без интерактивных
  жестов; перекрёстный порядок колбэков двух контроллеров при push не спрашивается.
- **Смена темы** в задаче про счётчики считается обычной сменой конфигурации, пока экран
  открыт; возврат из фона после смены конфигурации не используется (там есть нюансы).
- **Шаблоны «вручную»** (6 штук) держатся на справочных данных; если платформа изменит
  правила (новый dangerous-permission, новые требования магазинов), их нужно обновить.
