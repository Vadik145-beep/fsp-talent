// Запись демо-видео fsp-talent на стенде через Playwright.
//
//   node docs/demo/record_demo.cjs <фаза> [--out DIR]
//   фазы: register | candidate | recruiter | invite | accept | apply | admin  (по порядку; состояние — в DIR/state.json)
//
// Каждая фаза пишет своё видео DIR/<фаза>.webm и разметку DIR/<фаза>.events.json:
// где вырезать паузы ожидания (cut) и где ускорить (speed). Склейка — docs/demo/edit_demo.cjs.
//
// Тест соискателя проходится «с оператором»: на каждой задаче скрипт пишет DIR/q_<N>.json
// (условие задачи) и ждёт DIR/a_<N>.json с ответом. Форматы ответа:
//   {"choice":[0,2]}  — номера вариантов (с нуля)    {"raw":"42"}   — число
//   {"text":"..."}    — короткий ответ / вывод кода  {"line":3}     — строка с ошибкой
//   {"order":["id1","id2",...]} — порядок шагов      {"skip":true}  — «Не знаю»
// Нет ответа за ANSWER_WAIT_SEC — нажимается «Не знаю». Ожидание в итоговое видео не попадает.
//
// Переменные окружения: BASE (стенд), PW_MODULE (путь к пакету playwright), ANSWER_WAIT_SEC.
const fs = require('fs')
const path = require('path')
const { chromium } = require(process.env.PW_MODULE || 'playwright')

const BASE = process.env.BASE || 'https://159-194-200-243.sslip.io'
const ANSWER_WAIT_SEC = Number(process.env.ANSWER_WAIT_SEC || 100)
const ROOT = path.resolve(__dirname, '../..')
const RESUME = path.join(ROOT, 'data/samples/resumes/01_backend_python_middle.pdf')
const PHASE = process.argv[2]
const outIdx = process.argv.indexOf('--out')
const OUT = path.resolve(outIdx > 0 ? process.argv[outIdx + 1] : path.join(process.cwd(), 'demo-out'))
fs.mkdirSync(OUT, { recursive: true })
const STATE_FILE = path.join(OUT, 'state.json')
const state = fs.existsSync(STATE_FILE) ? JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')) : {}
const saveState = () => fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2))

const DEMO_PASSWORD = 'demo-video-2026'
const W = 1440
const H = 900

// ---------- оверлеи в браузере: курсор, подсветка клика, титры ----------
const INIT = `(() => {
  if (window.__demoInit) return; window.__demoInit = true;
  const css = \`
    #__cur{position:fixed;left:-50px;top:-50px;width:24px;height:24px;margin:-12px 0 0 -12px;border-radius:50%;
      background:rgba(64,47,255,.28);border:2px solid #402FFF;z-index:2147483647;pointer-events:none;
      transition:transform .12s ease;box-shadow:0 0 0 2px rgba(255,255,255,.9)}
    .__ripple{position:fixed;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;border:3px solid #EC1D35;
      z-index:2147483646;pointer-events:none;animation:__rip .6s ease-out forwards}
    @keyframes __rip{to{transform:scale(4);opacity:0}}
    #__title{position:fixed;inset:0;z-index:2147483645;display:flex;flex-direction:column;align-items:center;
      justify-content:center;background:rgba(27,28,33,.86);backdrop-filter:blur(6px);color:#fff;text-align:center;
      font-family:'JetBrains Mono','Inter',system-ui,sans-serif;animation:__fade .35s ease}
    #__title .n{font-size:28px;color:#C8C9CA;margin-bottom:18px;letter-spacing:.08em}
    #__title .t{font-size:52px;font-weight:700;max-width:1200px;line-height:1.2}
    #__title .s{font-family:'Inter',system-ui,sans-serif;font-size:24px;color:#EDEDED;margin-top:22px;max-width:1100px;line-height:1.4}
    #__title .bar{width:120px;height:6px;background:#402FFF;border-radius:3px;margin-top:30px}
    #__badge{position:fixed;right:24px;bottom:24px;z-index:2147483644;background:#402FFF;color:#fff;
      font:600 18px 'Inter',system-ui,sans-serif;padding:10px 16px;border-radius:10px;box-shadow:0 6px 20px rgba(0,0,0,.25)}
    @keyframes __fade{from{opacity:0}to{opacity:1}}\`;
  const install = () => {
    if (document.getElementById('__cur')) return;
    const st = document.createElement('style'); st.textContent = css; document.documentElement.appendChild(st);
    const c = document.createElement('div'); c.id = '__cur'; document.documentElement.appendChild(c);
    try { const p = JSON.parse(sessionStorage.getItem('__curpos') || 'null'); if (p) { c.style.left = p[0] + 'px'; c.style.top = p[1] + 'px' } } catch (e) {}
    addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px';
      try { sessionStorage.setItem('__curpos', JSON.stringify([e.clientX, e.clientY])) } catch (er) {} }, true);
    addEventListener('mousedown', (e) => { c.style.transform = 'scale(.6)';
      const r = document.createElement('div'); r.className = '__ripple'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
      document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700) }, true);
    addEventListener('mouseup', () => { c.style.transform = '' }, true);
  };
  window.__title = (n, t, s) => { window.__untitle(); const d = document.createElement('div'); d.id = '__title';
    d.innerHTML = (n ? '<div class="n"></div>' : '') + '<div class="t"></div>' + (s ? '<div class="s"></div>' : '') + '<div class="bar"></div>';
    if (n) d.querySelector('.n').textContent = n; d.querySelector('.t').textContent = t; if (s) d.querySelector('.s').textContent = s;
    document.documentElement.appendChild(d) };
  window.__untitle = () => { const d = document.getElementById('__title'); if (d) d.remove() };
  window.__badge = (t) => { let b = document.getElementById('__badge'); if (!t) { if (b) b.remove(); return }
    if (!b) { b = document.createElement('div'); b.id = '__badge'; document.documentElement.appendChild(b) } b.textContent = t };
  window.__smoothScroll = (to, ms) => new Promise((res) => { const from = scrollY; const d = to - from; const t0 = performance.now();
    const step = (t) => { const k = Math.min(1, (t - t0) / ms); const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      scrollTo(0, from + d * e); k < 1 ? requestAnimationFrame(step) : res() }; requestAnimationFrame(step) });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})()`

// ---------- разметка видео ----------
let T0 = 0
const events = []
const now = () => (Date.now() - T0) / 1000
const ev = (type, extra = {}) => events.push({ t: Number(now().toFixed(2)), type, ...extra })
const log = (...a) => console.log(`[${now().toFixed(1)}]`, ...a)

let page
let ctx
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const pause = (ms = 700) => page.waitForTimeout(ms)
let mouse = [W / 2, H / 2]

async function moveTo(x, y, steps = 18) {
  await page.mouse.move(x, y, { steps })
  mouse = [x, y]
}

async function hover(loc) {
  await loc.scrollIntoViewIfNeeded()
  const b = await loc.boundingBox()
  if (!b) return
  await moveTo(b.x + Math.min(b.width / 2, 120), b.y + b.height / 2)
}

async function click(loc, { wait = 450 } = {}) {
  await loc.waitFor({ state: 'visible', timeout: 20000 })
  await ensureVisible(loc)
  await hover(loc)
  await pause(180)
  await loc.click()
  await pause(wait)
}

async function type(loc, text, delay = 28) {
  await click(loc, { wait: 150 })
  await loc.pressSequentially(text, { delay })
  await pause(250)
}

async function ensureVisible(loc) {
  const b = await loc.boundingBox()
  if (!b) return
  if (b.y < 70 || b.y + b.height > H - 30) {
    const y = await page.evaluate(() => scrollY)
    const target = Math.max(0, y + b.y - H / 3)
    await page.evaluate(([t, ms]) => window.__smoothScroll(t, ms), [target, 700])
    await pause(150)
  }
}

async function scrollToLoc(loc, offset = 120, ms = 900) {
  const b = await loc.boundingBox()
  if (!b) return
  const y = await page.evaluate(() => scrollY)
  await page.evaluate(([t, m]) => window.__smoothScroll(t, m), [Math.max(0, y + b.y - offset), ms])
  await pause(250)
}

async function scrollBy(dy, ms = 1200) {
  await page.evaluate(([d, m]) => window.__smoothScroll(scrollY + d, m), [dy, ms])
  await pause(250)
}

async function scrollTop(ms = 600) {
  await page.evaluate((m) => window.__smoothScroll(0, m), ms)
}

async function title(n, t, s, ms = 2800) {
  ev('title', { text: t })
  await page.evaluate(([a, b, c]) => window.__title(a, b, c), [n, t, s])
  await pause(ms)
  await page.evaluate(() => window.__untitle())
  await pause(300)
}

function cutStart(why) {
  ev('cut_start', { why })
}
function cutEnd() {
  ev('cut_end')
}

async function login(email, password) {
  cutStart('вход ' + email)
  await ctx.clearCookies()
  await page.goto(BASE + '/login')
  await page.evaluate(() => { try { sessionStorage.clear() } catch (e) {} })
  await page.locator('input[type=email]').fill(email)
  await page.locator('input[autocomplete=current-password]').fill(password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL((u) => !u.pathname.startsWith('/login'), { timeout: 20000 })
  await page.waitForLoadState('networkidle').catch(() => {})
}

async function gotoQuiet(url, waitFor) {
  await page.goto(BASE + url)
  if (waitFor) await waitFor()
  await page.waitForLoadState('networkidle').catch(() => {})
  await pause(400)
}

// ---------- фаза 1: регистрация и подтверждение почты ----------
async function phaseRegister() {
  const stamp = new Date().toISOString().replace(/[-:T]/g, '').slice(0, 12)
  state.email = `demo.video.${stamp}@example.com`
  state.password = DEMO_PASSWORD
  state.fullName = 'Денис Морозов'
  saveState()
  log('почта', state.email)

  cutStart('загрузка')
  await gotoQuiet('/', () => page.getByText('Ищу работу').first().waitFor())
  cutEnd()
  await title('fsp-talent', 'Платформа подбора IT-специалистов', 'Категория из адаптивного теста → работодатель находит кандидата сам → приглашение с вилкой', 3600)
  await pause(800)
  await title('Блок 1', 'Регистрация соискателя', 'Почта с подтверждением и согласие на обработку ПДн')
  ev('speed_start', { factor: 2 }) // ввод формы и демо-почта — ускоренно

  const cta = page.getByRole('link', { name: /Ищу работу/ }).first()
  if (await cta.count()) await click(cta)
  else await page.goto(BASE + '/register?role=candidate')
  await page.waitForURL(/register/)
  await pause(600)
  await type(page.getByLabel(/Имя и фамилия/), state.fullName)
  await type(page.locator('input[type=email]'), state.email, 18)
  await type(page.locator('input[autocomplete=new-password]'), state.password, 30)
  await click(page.getByText('Согласен на обработку персональных данных'))
  await click(page.getByRole('button', { name: 'Зарегистрироваться' }))
  await page.waitForURL(/verify-email/, { timeout: 20000 })
  await pause(1800)

  // письмо в демо-почте
  await page.goto(BASE + '/mail/')
  await page.waitForLoadState('networkidle').catch(() => {})
  await pause(800)
  const search = page.getByPlaceholder(/Search/i).first()
  await type(search, state.email, 10)
  await page.keyboard.press('Enter')
  await pause(1500)
  const row = page.locator('a.message, .message').filter({ hasText: state.email }).first()
  await click((await row.count()) ? row : page.getByText(state.email).first(), { wait: 1500 })
  const frame = page.frameLocator('iframe').first()
  const link = frame.locator('a[href*="verify-email"]').first()
  await link.waitFor({ timeout: 15000 })
  await pause(1200)
  await hover(link)
  await pause(500)
  const href = await link.getAttribute('href')
  state.verifyLink = href
  saveState()
  await page.mouse.down()
  await page.mouse.up()
  await page.goto(href)
  await page.getByRole('heading', { name: 'Почта подтверждена' }).waitFor({ timeout: 20000 })
  ev('speed_end')
  await pause(2500)
}

// ---------- фаза 2: вход, онбординг, тест, категория ----------
async function phaseCandidate() {
  cutStart('загрузка')
  await gotoQuiet('/login', () => page.locator('input[type=email]').waitFor())
  cutEnd()
  await type(page.locator('input[type=email]'), state.email, 12)
  await type(page.locator('input[autocomplete=current-password]'), state.password, 25)
  await click(page.getByRole('button', { name: 'Войти', exact: true }))
  await page.waitForURL(/candidate/, { timeout: 20000 })
  if (!/onboarding/.test(page.url())) {
    await pause(1500)
    cutStart('переход в онбординг')
    await page.goto(BASE + '/candidate/onboarding')
  }
  await page.getByText('Как заполним профиль?').waitFor({ timeout: 20000 })
  cutEnd()
  await pause(800)

  // профиль из PDF
  await title('Блок 2', 'Профиль, опрос и адаптивный тест', 'PDF-резюме разбирается правилами, опрос подсказывает специализацию, тест подстраивается под уровень')
  ev('speed_start', { factor: 2 }) // профиль и опрос — ускоренно
  await click(page.getByRole('button', { name: /Загрузить PDF-резюме/ }))
  const pick = page.getByRole('button', { name: /Выбрать PDF/ })
  await hover(pick)
  await pause(400)
  await page.mouse.down()
  await page.mouse.up()
  await page.locator('input[type=file]').setInputFiles(RESUME)
  await page.getByText(/Заполнили из/).waitFor({ timeout: 30000 })
  await pause(1500)
  await scrollBy(450, 1500)
  await pause(800)
  const hybrid = page.getByRole('button', { name: 'Гибрид', exact: true }).first()
  if ((await hybrid.getAttribute('aria-pressed')) !== 'true') await click(hybrid, { wait: 600 })
  await scrollBy(450, 1500)
  await pause(800)
  // ссылка из резюме приходит без https:// — форма её не пропускает, дописываем
  const linkInput = page.getByLabel('Адрес ссылки').first()
  if ((await linkInput.count()) && !/^https?:\/\//.test(await linkInput.inputValue())) {
    await click(linkInput, { wait: 150 })
    await page.keyboard.press('Home')
    await page.keyboard.type('https://', { delay: 40 })
    await pause(400)
  }
  await click(page.getByRole('button', { name: 'Сохранить и продолжить' }))

  // опрос
  await page.getByText('Опрос по специализации').waitFor({ timeout: 20000 })
  await pause(800)
  const picks = ['Писать серверную логику и API', 'Python', 'SQL', 'Ускорить медленный запрос к базе', '2–5 лет',
    'Исполнитель задач', 'Архитектуру распределённых систем', 'На сервере']
  for (const p of picks) await click(page.getByText(p, { exact: true }).first(), { wait: 250 })
  await type(page.locator('textarea').last(), 'Платёжный сервис на FastAPI и PostgreSQL', 22)
  await click(page.getByRole('button', { name: 'Узнать рекомендацию' }))
  await page.getByText('Рекомендуем специализацию').waitFor({ timeout: 20000 })
  ev('speed_end')
  await pause(2500)
  await click(page.getByRole('button', { name: /Дальше: выбор грейда/ }))
  await pause(800)
  await click(page.locator('label').filter({ hasText: /^Middle/ }).first())
  await pause(1500)
  await click(page.getByRole('button', { name: /Дальше: тест/ }))
  await page.getByRole('button', { name: 'Начать тест' }).waitFor()
  await pause(2500)

  // тест
  let lastItem = null
  page.on('response', async (r) => {
    if (!/\/api\/testing\/sessions/.test(r.url())) return
    try {
      const j = await r.json()
      const it = j.current_item || j.next_item
      if (it) lastItem = { item: it, number: j.item_number || (j.answered != null ? j.answered + 1 : null) }
      if (j.session && j.session.id) state.sessionId = j.session.id
    } catch (e) {}
  })
  await click(page.getByRole('button', { name: 'Начать тест' }))
  await page.waitForURL(/\/candidate\/test\/\d+/, { timeout: 20000 })
  let n = 0
  let seen = new Set()
  while (true) {
    // ждём новую задачу или страницу результата
    const t0 = Date.now()
    while (Date.now() - t0 < 30000) {
      if (/\/result/.test(page.url())) break
      if (lastItem && !seen.has(lastItem.item.instance_id)) break
      await sleep(200)
    }
    if (/\/result/.test(page.url())) break
    if (!lastItem || seen.has(lastItem.item.instance_id)) throw new Error('нет новой задачи')
    const { item } = lastItem
    seen.add(item.instance_id)
    n += 1
    await page.getByRole('heading', { name: `Задача ${n}` }).waitFor({ timeout: 15000 })
    const fast = n >= 4 && n <= 18
    await page.evaluate((t) => window.__badge(t), fast ? 'Задачи 4–18 — ускорено' : null)
    ev('item_start', { n })
    if (fast) ev('speed_start', { factor: 6 })
    await pause(fast ? 300 : 1500)
    const waitSec = Math.min(ANSWER_WAIT_SEC, (item.time_limit_sec || 120) - 20)
    const qf = path.join(OUT, `q_${n}.json`)
    const af = path.join(OUT, `a_${n}.json`)
    cutStart('ответ оператора') // до записи файла: запись на Windows иногда тормозит на секунды
    fs.writeFileSync(qf + '.tmp', JSON.stringify({ n, item }, null, 2))
    fs.renameSync(qf + '.tmp', qf)
    log('задача', n, item.format, '— жду', af)
    let ans = null
    const w0 = Date.now()
    while (Date.now() - w0 < waitSec * 1000) {
      if (fs.existsSync(af)) {
        try { ans = JSON.parse(fs.readFileSync(af, 'utf8')); break } catch (e) {}
      }
      await sleep(300)
    }
    cutEnd()
    await answerItem(item, ans || { skip: true })
    if (fast) ev('speed_end')
    ev('item_end', { n })
    state.items = n
    saveState()
  }
  await page.evaluate(() => window.__badge(null))
  cutStart('результат грузится')
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.getByText(/Backend|Frontend|Mobile|QA|DevOps|Data Science/).first().waitFor({ timeout: 20000 })
  await pause(800)
  cutEnd()
  await title('Блок 3', 'Категория и грейд', 'Категорию присваивает только тест. Правильные ответы не показываем — банк не утекает')
  await pause(2000)
  await scrollBy(420, 1600)
  await pause(1800)
  await scrollBy(420, 1600)
  await pause(1800)
  await scrollTop(800)
  await pause(800)

  // публикация профиля
  await click(page.getByRole('link', { name: 'Настройки' }).first())
  await page.getByText('Публикация профиля работодателям').waitFor({ timeout: 20000 })
  await pause(800)
  await scrollToLoc(page.getByText('Публикация профиля работодателям'), 250)
  await click(page.getByText('Публикация профиля работодателям'), { wait: 1500 })
  const pseud = page.getByText(/Кандидат #[0-9A-F]{4}/).first()
  await pseud.waitFor({ timeout: 10000 }).catch(() => {})
  if (await pseud.count()) {
    await scrollToLoc(pseud, 300)
    state.pseudonym = (await pseud.textContent()).match(/#[0-9A-F]{4}/)[0]
  }
  await pause(2500)
  saveState()
  log('псевдоним', state.pseudonym)
}

async function answerItem(item, a) {
  if (a.skip) {
    await click(page.getByRole('button', { name: 'Не знаю' }), { wait: 900 })
    return
  }
  const f = item.format
  if (f === 'single_choice' || f === 'multiple_choice') {
    for (const i of a.choice) {
      const opt = item.options[i]
      await click(page.locator('label').filter({ hasText: opt.text }).first(), { wait: 250 })
    }
  } else if (f === 'numeric') {
    await type(page.getByLabel(/Ваш ответ/), String(a.raw), 60)
  } else if (f === 'short_text') {
    await type(page.getByLabel(/Ваш ответ/), a.text, 45)
  } else if (f === 'code_output') {
    await type(page.getByLabel(/Что выведет программа/), a.text, 60)
  } else if (f === 'find_error_line') {
    await click(page.locator(`button[aria-label^="Строка ${a.line}:"]`))
  } else if (f === 'ordering') {
    const byId = Object.fromEntries(item.steps.map((s) => [s.id, s.text]))
    let cur = item.steps.map((s) => s.id)
    let moved = false
    for (let i = 0; i < a.order.length; i++) {
      let j = cur.indexOf(a.order[i])
      while (j > i) {
        await click(page.getByRole('button', { name: `Поднять шаг «${byId[cur[j]]}»` }), { wait: 200 })
        ;[cur[j - 1], cur[j]] = [cur[j], cur[j - 1]]
        j -= 1
        moved = true
      }
    }
    if (!moved) await hover(page.getByRole('list', { name: 'Шаги по порядку' }))
  }
  await pause(500)
  await click(page.getByRole('button', { name: 'Ответить' }), { wait: 900 })
}

// ---------- фаза 3: рекрутер — потребность, подборка, профиль кандидата ----------
const NEED_TEXT = 'Ищем middle Python-разработчика в платёжный сервис: FastAPI и PostgreSQL обязательно, Redis будет плюсом. Гибрид, 250–320 тысяч.'

async function phaseRecruiter() {
  await login('recruiter@example.com', 'demo1234')
  await gotoQuiet('/recruiter', () => page.getByRole('link', { name: /Новая потребность/ }).first().waitFor())
  cutEnd()
  await title('Блок 4', 'Работодатель: потребность → подборка с объяснением', 'Рекрутер описывает, кого ищет, своими словами — платформа раскладывает текст по полям')
  await pause(1200)
  await click(page.getByRole('link', { name: /Новая потребность/ }).first())
  await page.getByLabel(/Опишите, кого ищете/).waitFor()
  await pause(600)
  await type(page.getByLabel(/Опишите, кого ищете/), NEED_TEXT, 14)
  await click(page.getByRole('button', { name: 'Разобрать' }))
  await page.getByText(/Распознано/).waitFor({ timeout: 20000 })
  await pause(2000)
  await scrollBy(380, 1400)
  await pause(1500)
  await scrollBy(380, 1400)
  await pause(1200)
  const from = page.getByLabel('От', { exact: true })
  if (!(await from.inputValue())) await type(from, '250000')
  const to = page.getByLabel('До', { exact: true })
  if (!(await to.inputValue())) await type(to, '320000')
  await click(page.getByRole('button', { name: /Подобрать кандидатов/ }))
  await page.waitForURL(/\/recruiter\/needs\/\d+/, { timeout: 20000 })
  state.needId = Number(page.url().match(/needs\/(\d+)/)[1])
  saveState()
  await page.getByText(/по убыванию соответствия/).waitFor({ timeout: 20000 })
  await pause(2500)
  const how = page.getByText('Как считается соответствие')
  await click(how, { wait: 2500 })
  await scrollBy(300, 1200)
  await pause(1500)

  const code = state.pseudonym
  let card = code
    ? page.getByText(`Кандидат ${code}`, { exact: true }).first()
        .locator('xpath=ancestor::*[.//*[normalize-space(text())="Открыть профиль"]][1]')
    : null
  if (!card || !(await card.count())) {
    log('нового кандидата нет в основной категории — ищу в соседних')
    card = null
  }
  if (card) {
    await scrollToLoc(card, 90, 1400)
    await pause(3000)
    await scrollBy(250, 1000)
    await pause(1500)
    await click(card.getByRole('link', { name: /Открыть профиль/ }).or(card.getByRole('button', { name: /Открыть профиль/ })).first())
  } else {
    const first = page.getByRole('link', { name: /Открыть профиль/ }).or(page.getByRole('button', { name: /Открыть профиль/ })).first()
    await scrollToLoc(first, 400)
    await click(first)
  }
  await page.waitForURL(/\/recruiter\/candidates\/\d+/, { timeout: 20000 })
  state.candidateId = Number(page.url().match(/candidates\/(\d+)/)[1])
  saveState()
  await page.getByText('Результат теста').first().waitFor({ timeout: 20000 })
  await pause(2000)
  await scrollBy(400, 1500)
  await pause(1800)
  await scrollTop(800)
  await pause(600)
}

// ---------- фаза 4: приглашение с вилкой ----------
async function phaseInvite() {
  await login('recruiter@example.com', 'demo1234')
  await gotoQuiet(`/recruiter/candidates/${state.candidateId}`, () => page.getByText('Результат теста').first().waitFor({ timeout: 20000 }))
  cutEnd()
  await title('Блок 5', 'Приглашение с вилкой', 'Зарплата «от–до» обязательна. Контакты откроются, только когда кандидат примет приглашение')
  await click(page.getByRole('button', { name: /Пригласить/ }).first())
  const dlg = page.getByRole('dialog')
  await dlg.waitFor()
  await pause(1500)
  // поля вилки заполнены подсказкой — меняем на свою вилку
  for (const [label, value] of [['От', '260000'], ['До', '340000']]) {
    const input = dlg.getByLabel(label, { exact: true })
    await click(input, { wait: 150 })
    await page.keyboard.press('Control+A')
    await page.keyboard.press('Backspace')
    await page.keyboard.type(value, { delay: 70 })
    await pause(500)
  }
  await pause(2500)
  await click(dlg.getByRole('button', { name: /Отправить приглашение/ }))
  await dlg.waitFor({ state: 'hidden', timeout: 15000 })
  await pause(2500)
}

// ---------- фаза 5: соискатель принимает, рекрутер видит контакты ----------
async function phaseAccept() {
  await login(state.email, state.password)
  await gotoQuiet('/candidate/invitations', () => page.getByText(/Северный код/).first().waitFor({ timeout: 20000 }))
  cutEnd()
  await pause(1500)
  await click(page.getByRole('link').filter({ hasText: /Северный код/ }).first())
  await page.getByRole('button', { name: /^Принять/ }).first().waitFor({ timeout: 20000 })
  await pause(2500)
  await click(page.getByRole('button', { name: /^Принять/ }).first())
  const dlg = page.getByRole('dialog')
  await dlg.waitFor()
  await pause(1500)
  await click(dlg.getByRole('button', { name: /Принять и открыть контакты/ }))
  await dlg.waitFor({ state: 'hidden', timeout: 15000 })
  await pause(3000)

  await login('recruiter@example.com', 'demo1234')
  await gotoQuiet(`/recruiter/candidates/${state.candidateId}`, () => page.getByText('Контакты открыты').waitFor({ timeout: 20000 }))
  cutEnd()
  await pause(1000)
  await hover(page.getByText('Контакты открыты'))
  await pause(3500)
}

// ---------- фаза 6: отклик на вакансию ----------
async function phaseApply() {
  await login(state.email, state.password)
  await gotoQuiet('/candidate/vacancies', () => page.getByText('Middle Python-разработчик', { exact: true }).waitFor({ timeout: 20000 }))
  cutEnd()
  await title('Блок 6', 'Отклик на вакансию', 'Классический путь тоже есть: откликнулся сам — работодатель сразу видит контакты')
  const card = page.locator('div').filter({ has: page.getByText('Middle Python-разработчик', { exact: true }) }).filter({ has: page.getByRole('button', { name: 'Откликнуться' }) }).last()
  await scrollToLoc(card, 200, 1200)
  await pause(1500)
  await click(card.getByRole('button', { name: 'Откликнуться' }))
  const dlg = page.getByRole('dialog')
  await dlg.waitFor()
  await type(dlg.locator('textarea'), 'Пять лет пишу платёжные сервисы на FastAPI и PostgreSQL — готов обсудить.', 16)
  await pause(1200)
  await click(dlg.getByRole('button', { name: 'Отправить отклик' }))
  await dlg.waitFor({ state: 'hidden', timeout: 15000 })
  await pause(2500)

  await login('recruiter@example.com', 'demo1234')
  await gotoQuiet('/recruiter/vacancies', () => page.getByRole('tab', { name: /Отклики/ }).waitFor({ timeout: 20000 }))
  cutEnd()
  await pause(1200)
  await click(page.getByRole('tab', { name: /Отклики/ }), { wait: 1500 })
  const mine = page.getByText(/Морозов/).first()
  await mine.waitFor({ timeout: 15000 }).catch(() => {})
  if (await mine.count()) await hover(mine)
  await pause(4000)
}

// ---------- фаза 7: админ — банк задач и валидация ----------
async function phaseAdmin() {
  await login('admin@example.com', 'demo1234')
  await gotoQuiet('/admin/items', () => page.getByText(/[a-z]{2}-[a-z]+-\d{3} · /).first().waitFor({ timeout: 40000 }))
  cutEnd()
  await title('Блок 7', 'Механика теста', 'Банк параметрических шаблонов: у каждого кандидата свой вариант, сложность по IRT, детектор утечек')
  await pause(1500)
  await scrollBy(350, 1300)
  await pause(1500)
  await scrollTop(700)
  const searchBox = page.getByPlaceholder(/Название или код шаблона/)
  await type(searchBox, 'mo-lang-013', 40)
  await pause(1500)
  const rowLink = page.getByText(/Срезы списков/).first()
  if (await rowLink.count()) {
    await click(rowLink, { wait: 800 })
  }
  if (!/\/admin\/items\/\d+/.test(page.url())) await page.goto(BASE + '/admin/items/13')
  await page.getByText(/Три кандидата/).waitFor({ timeout: 20000 })
  await pause(2500)
  await hover(page.getByText(/Возможная утечка/).first())
  await pause(2500)
  await scrollToLoc(page.getByText(/Три кандидата/).first(), 120, 1400)
  await pause(1000)
  for (const k of [1, 2, 3]) {
    await hover(page.getByText(`Кандидат ${k}`, { exact: true }).first())
    await pause(1300)
  }
  await pause(1500)

  await title('Блок 8', 'Валидация', 'Синтетика с известной правдой: 1200 кандидатов, 100 потребностей, сравнение с поиском по словам')
  await click(page.getByRole('link', { name: 'Валидация' }).first())
  await page.waitForURL(/validation/)
  await page.waitForLoadState('networkidle').catch(() => {})
  await pause(3000)
  for (let i = 0; i < 4; i++) {
    await scrollBy(480, 1600)
    await pause(2200)
  }
  await scrollTop(1000)
  await pause(800)
  await title(null, 'fsp-talent', `Стенд: ${BASE.replace('https://', '')}  ·  демо-входы на странице входа`, 3500)
}

// ---------- запуск ----------
;(async () => {
  const phases = { register: phaseRegister, candidate: phaseCandidate, recruiter: phaseRecruiter, invite: phaseInvite, accept: phaseAccept, apply: phaseApply, admin: phaseAdmin }
  if (!phases[PHASE]) {
    console.error('Фаза: ' + Object.keys(phases).join(' | '))
    process.exit(2)
  }
  const browser = await chromium.launch({ slowMo: 40 })
  const vdir = path.join(OUT, 'raw-' + PHASE)
  fs.mkdirSync(vdir, { recursive: true })
  ctx = await browser.newContext({
    viewport: { width: W, height: H },
    recordVideo: { dir: vdir, size: { width: W, height: H } },
    locale: 'ru-RU',
  })
  await ctx.addInitScript(INIT)
  page = await ctx.newPage()
  T0 = Date.now()
  const errors = []
  page.on('pageerror', (e) => errors.push(String(e)))
  let failed = null
  try {
    await phases[PHASE]()
  } catch (e) {
    failed = e
    console.error('ПАДЕНИЕ:', e.message)
    await page.screenshot({ path: path.join(OUT, `fail-${PHASE}.png`) }).catch(() => {})
  }
  ev('end')
  const video = page.video()
  await ctx.close()
  await browser.close()
  const src = await video.path()
  const dst = path.join(OUT, `${PHASE}.webm`)
  fs.copyFileSync(src, dst)
  fs.writeFileSync(path.join(OUT, `${PHASE}.events.json`), JSON.stringify({ phase: PHASE, video: `${PHASE}.webm`, events }, null, 2))
  console.log('видео:', dst, '| ошибки страницы:', errors.length ? errors : 'нет')
  if (failed) process.exit(1)
})()
