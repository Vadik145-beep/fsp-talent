# Банк задач: Frontend

30 параметрических шаблонов (T4.3). Код: `backend/app/testing/engine/bank/frontend/`
(модули по темам: `js_semantics.py`, `js_async.py`, `css_layout.py`, `dom_events.py`, `react.py`,
`browser_net.py`, `typescript.py`, `security_a11y.py`), тесты:
`backend/tests/engine/test_bank_frontend_models.py` (состав и независимые расчёты) и
`backend/tests/engine/test_bank_frontend_runtime.py` (сверка с node, jsdom, React, tsc).
Примеры из `bank_examples` (порядок микрозадач и таймеров, специфичность CSS) сюда не входят,
их механика не повторяется.

Каждый шаблон даёт не меньше 100 разных вариантов на 300 seed (на деле почти все — по варианту
на seed); ответ вычисляет генератор, а не таблица. Условия однозначные: в задачах указано
окружение (Node.js, современный Chrome, React 18 без StrictMode, TypeScript 5 strict).
Стартовые `a`, `b` заданы экспертно по грейду и уточняются калибровкой.

## Шаблоны

Как сверен ответ:
- **node** — код варианта запускается в Node.js как есть, вывод сравнивается с ключом;
- **jsdom** — HTML и JS варианта выполняются в jsdom (реализация спецификации DOM), лог
  обработчиков сравнивается с ключом;
- **React** — компонент из условия рендерится настоящим React 18.3 + react-dom в jsdom
  (JSX через sucrase), действия пользователя — клики и ввод, результат сравнивается с ключом;
- **tsc** — вариант компилируется TypeScript 5 (`strict: true`): ошибка ровно одна и в строке-
  ключе / тип `R` совпадает ровно с одним вариантом ответа — верным;
- **модель** — вторая, независимая реализация в тесте: заново разбирает CSS/HTML/формулировку
  варианта и считает другим алгоритмом;
- **вручную** — ключ сверен по спецификации/документации, в тесте — эталонная таблица.

| id | тема | формат | грейд | a | b | что проверяет | как сверен ответ |
|---|---|---|---|---|---|---|---|
| frontend.js_coercion | javascript | code_output | intern | 1.1 | −1.6 | `+` со строкой, `-`/`*`/`/` с приведением, `null`/`undefined` в арифметике, `[a]+[b]`, сравнение строк | node |
| frontend.js_array_methods | javascript | code_output | intern | 1.2 | −1.2 | filter/map/reduce/find/indexOf/slice/some/every, `sort()` без компаратора, splice меняет массив | node |
| frontend.js_loose_equality | javascript | multi_choice | junior | 1.2 | −0.5 | какие выражения с `==` дают true: `null`, `NaN`, массивы, пробелы в строке, `null >= 0` | node (каждое выражение вычисляется) |
| frontend.js_closures_loop | javascript | code_output | junior | 1.4 | −0.7 | замыкания в циклах: var, let, IIFE, переменная вне цикла, const-копия, setTimeout и массив функций | node |
| frontend.js_object_copy | javascript | code_output | junior | 1.3 | −0.3 | ссылка, spread, Object.assign, structuredClone, JSON: что меняется в оригинале | node |
| frontend.js_this_binding | javascript | code_output | middle | 1.5 | 0.6 | this в strict: извлечённый метод, call/bind (bind сильнее call), стрелочное поле класса, function внутри map, `(0, obj.m)()` | node |
| frontend.js_promise_chain | javascript_async | code_output | middle | 1.5 | 0.4 | цепочка then/catch/finally: куда уходит ошибка, что возвращает catch, finally не меняет значение, then с двумя аргументами | node |
| frontend.js_promise_combinators | javascript_async | code_output | senior | 1.6 | 1.2 | Promise.all/race/allSettled/any: порядок значений, первая по времени ошибка, AggregateError, обычное значение в массиве | node |
| frontend.css_box_sizing | css | numeric | intern | 1.3 | −1.4 | ширина рамки/содержимого/с margin при content-box и border-box, сокращения padding/border-width, глобальный `*{box-sizing}` | модель |
| frontend.css_grid_fr | css | numeric | junior | 1.3 | −0.6 | ширина колонки: px, %, fr, `repeat()`, gap | модель |
| frontend.css_flex_distribution | css | numeric | middle | 1.4 | 0.8 | flex-grow/shrink/basis, `flex: N` = N 1 0%, `flex: auto`/`none`, width при basis auto, gap, сжатие по shrink × basis | модель (алгоритм §9.7 с заморозкой) |
| frontend.css_margin_collapse | css | numeric | middle | 1.3 | 0.3 | схлопывание margin: соседи, отрицательные, через пустой блок и через родителя; padding/border/overflow/flow-root/flex мешают | модель (блочная раскладка) |
| frontend.css_stacking_context | css | single_choice | senior | 1.5 | 1.5 | кто сверху: контекст наложения (position+z-index, opacity, transform), z-index без position, отрицательный z-index | модель (отрисовка по CSS 2.1 Appendix E) |
| frontend.dom_target_delegation | dom_events | code_output | intern | 1.2 | −1.1 | делегирование: target, currentTarget, this, closest, dataset у вложенного элемента | jsdom |
| frontend.dom_event_phases | dom_events | ordering | junior | 1.4 | −0.2 | порядок обработчиков: погружение, цель (capture раньше bubble), всплытие, порядок регистрации | jsdom |
| frontend.dom_stop_propagation | dom_events | code_output | middle | 1.4 | 0.5 | stopPropagation против stopImmediatePropagation, preventDefault не останавливает, `once` при двух кликах | jsdom |
| frontend.react_hook_choice | react | short_text | intern | 1.1 | −1.3 | какой хук подставить: useRef, useEffect, useMemo, useCallback, useContext, useLayoutEffect, useId, useReducer | вручную (+ тест: ответы — реальные экспорты React 18) |
| frontend.react_state_batching | react | numeric | junior | 1.5 | −0.1 | несколько setState в обработчике: снимок значения против функционального обновления, один и два клика | React |
| frontend.react_list_keys | react | code_output | middle | 1.5 | 0.7 | key={index} против стабильного ключа: куда «уезжает» введённый в поле текст при удалении/перестановке | React |
| frontend.react_memo_renders | react | numeric | middle | 1.4 | 0.9 | сколько рендеров у memo-компонента: инлайн-объект/функция/массив, useCallback/useMemo с зависимостями, пропс меняется один раз | React |
| frontend.react_effect_order | react | ordering | senior | 1.6 | 1.6 | порядок render, useLayoutEffect, useEffect и cleanup при монтировании и обновлении, дети раньше родителя, `[]` не перезапускается | React |
| frontend.http_cache_headers | browser_network | short_text | junior | 1.1 | −0.8 | If-None-Match, If-Modified-Since, 304, no-store, no-cache, private, s-maxage, immutable, Vary, max-age | вручную (RFC 9110/9111) |
| frontend.cors_preflight | browser_network | multi_choice | middle | 1.3 | 0.2 | какие fetch вызовут preflight: методы, безопасные заголовки и Content-Type, JSON.stringify без заголовка, свой origin | модель (правила Fetch по тексту запроса) |
| frontend.script_loading_order | browser_network | ordering | senior | 1.4 | 1.3 | порядок выполнения: обычные, defer, type=module, async, DOMContentLoaded, load; defer/async у встроенных скриптов игнорируются | модель (правила HTML по разбору тегов) |
| frontend.cls_score | browser_network | numeric | senior | 1.2 | 1.9 | layout shift score = impact × distance fraction, обрезка окном, сдвиг по двум осям, два блока, исключение после ввода | модель (попиксельная маска numpy) + пример web.dev |
| frontend.ts_compile_error | typescript | find_bug_line | middle | 1.3 | 0.5 | ошибка strict: possibly undefined, сужение union, readonly, недостающее/лишнее свойство, unknown, литеральный тип, неявный any, необязательный колбэк | tsc |
| frontend.ts_conditional_types | typescript | single_choice | senior | 1.4 | 1.7 | распределение условного типа по union, `[T]`, never, infer, Exclude/Extract, keyof, индексный доступ, ReturnType | tsc |
| frontend.xss_sink | web_security | find_bug_line | junior | 1.3 | −0.4 | какая строка — XSS: innerHTML/outerHTML/insertAdjacentHTML/document.write/setTimeout со строкой/href; рядом безопасные textContent, value, setAttribute | вручную (+ тест: опасный приёмник ровно в строке-ключе) |
| frontend.cookie_samesite | web_security | multi_choice | senior | 1.3 | 1.1 | когда cookie уходит при Strict/Lax/None: ссылка, POST-форма, img, iframe, fetch с credentials, поддомен, адресная строка, http | вручную (эталонная таблица) |
| frontend.a11y_focusable | accessibility | multi_choice | intern | 1.0 | −1.8 | какие элементы попадут в порядок Tab: button, a[href], поля, summary, tabindex 0 против div onclick, a без href, disabled, hidden, tabindex −1 | вручную (HTML, эталонная таблица) |

Итого сверено: с настоящими системами — 17 (node 8, jsdom 3, React 4, tsc 2), независимой
моделью — 8, только вручную по спецификации — 5.

## Покрытие тем по грейдам

| тема | intern | junior | middle | senior | всего |
|---|---|---|---|---|---|
| javascript | 2 | 3 | 1 | — | 6 |
| javascript_async | — | — | 1 | 1 | 2 |
| css | 1 | 1 | 2 | 1 | 5 |
| dom_events | 1 | 1 | 1 | — | 3 |
| react | 1 | 1 | 2 | 1 | 5 |
| browser_network | — | 1 | 1 | 2 | 4 |
| typescript | — | — | 1 | 1 | 2 |
| web_security | — | 1 | — | 1 | 2 |
| accessibility | 1 | — | — | — | 1 |
| **всего** | **6** | **8** | **9** | **7** | **30** |

Форматы: code_output 10, numeric 7, multi_choice 4, ordering 3, short_text 2,
find_bug_line 2, single_choice 2.

## Как сверялись ответы

- **node.** `test_js_output_matches_node`: 30 seed на каждый JS-шаблон, код запускается
  `node -e`, вывод сравнивается проверкой движка (по токенам). Для `js_loose_equality` каждое
  выражение-вариант вычисляется в node, множество true-вариантов должно совпасть с ключом.
- **jsdom / React / tsc.** `test_bank_frontend_runtime.py` пишет node-обвязку во временную папку
  и прогоняет 40–80 вариантов за один запуск. Нужны npm-пакеты `jsdom@24 react@18.3.1
  react-dom@18.3.1 sucrase typescript@5`. Папка с `node_modules` берётся из переменной
  `FRONTEND_JS_TOOLS` или ищется выше по дереву в `_волны/tmp/*/frontend/js`; если пакетов нет,
  тесты пропускаются. Проверено на node 24.19, jsdom 24.1.3, React 18.3.1, sucrase 3.35.1,
  TypeScript 5.9.3. Установка: `npm install jsdom@24 react@18.3.1 react-dom@18.3.1 sucrase
  typescript@5` в любой папке вне репозитория и `FRONTEND_JS_TOOLS=<эта папка>`.
- **Модели в тесте** не импортируют генераторы: CSS и HTML разбираются из текста варианта.
  Flex — алгоритм «resolve flexible lengths» из спецификации с заморозкой; margin — обход
  дерева блоков с накоплением висящих margin (как в движках); наложение — рекурсивная
  отрисовка по Appendix E; CLS — попиксельная маска окна (numpy) по числам из формулировки.
  Модели дополнительно проверены эталонами из спецификаций (пример flex из CSS Flexbox, пример
  CLS с web.dev, два классических примера z-index).
- **Модели генераторов DOM и React** (`_dispatch_order`, `_effect_logs`) дополнительно
  сверены с ручными эталонами.

## Известные ограничения

- CSS проверен моделями, а не браузером. Генераторы берут только «чистые» случаи: у flex нет
  заморозки на min-width (элементы без содержимого, `min-width: 0`), у margin нет float и
  clearance, в задаче про наложение все элементы — блоки с фоном.
- Порядок скриптов сверен правилами HTML, а не браузером: jsdom не поддерживает модули.
- Порядок фаз на самой цели (capture раньше bubble) — по актуальной спецификации DOM
  (Chrome 89+); в условии указан современный Chrome. В задаче про stopPropagation на цели нет
  capture-обработчиков, чтобы не зависеть от этой детали.
- SameSite: в условии указано, что сторонние cookie не заблокированы, атрибут SameSite задан
  явно (поведение «Lax по умолчанию» и двухминутное исключение для POST не задействованы).
- Фокус по Tab: указан Chrome — в Safari по умолчанию Tab не переводит фокус на ссылки.
- short_text: принимаются основные написания (`304` / `304 Not Modified`, `N` / `max-age=N`,
  `useRef` / `React.useRef`, регистр не важен). Другие синонимы не принимаются.
- `react_hook_choice` ближе к знанию API, чем к разбору поведения; он стоит на уровне intern.
- `a`, `b` — экспертные стартовые значения, их уточнит калибровка по ответам.
