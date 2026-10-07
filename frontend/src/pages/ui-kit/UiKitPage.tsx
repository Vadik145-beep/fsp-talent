import { useState, type ReactNode } from 'react'
import { Info, Plus, RotateCw, Send, Trash2 } from 'lucide-react'
import {
  Avatar,
  Badge,
  BrandLines,
  brandAsset,
  Button,
  Card,
  CardHeader,
  Checkbox,
  Drawer,
  EmptyState,
  ErrorState,
  FilterBar,
  FspMark,
  FspVerifiedBadge,
  Input,
  Modal,
  PageHeader,
  Pagination,
  ProgressBar,
  Pseudonym,
  RadioGroup,
  SalaryRange,
  ScoreBar,
  Select,
  Skeleton,
  SkeletonCard,
  SkeletonText,
  StatusPill,
  Stepper,
  Switch,
  Table,
  Tabs,
  Tag,
  TagInput,
  Textarea,
  Timer,
  Tooltip,
  useToast,
  type TableColumn,
} from '@/shared/ui'
import {
  GRADE_OPTIONS,
  INVITATION_STATUSES,
  SPECIALIZATION_OPTIONS,
  categoryLabel,
  type InvitationStatus,
} from '@/shared/config/dictionaries'

const STACK = ['Python', 'FastAPI', 'Django', 'PostgreSQL', 'Go', 'Java', 'Kotlin', 'React', 'TypeScript', 'Vue', 'Docker', 'Kubernetes', 'Redis', 'Kafka']

const colorTokens: Array<{ name: string; value: string; text?: string }> = [
  { name: 'fsp-blue · primary', value: '#402FFF' },
  { name: 'fsp-red · accent', value: '#EC1D35' },
  { name: 'fsp-gray', value: '#EDEDED', text: '#1B1C21' },
  { name: 'fsp-silver · line-strong', value: '#C8C9CA', text: '#1B1C21' },
  { name: 'fsp-black · ink', value: '#1B1C21' },
  { name: 'fsp-blue-deep', value: '#2A1EB0' },
  { name: 'fsp-blue-pale · primary-tint', value: '#DCD9FF', text: '#1B1C21' },
  { name: 'danger (текст, кнопки)', value: '#C4122B' },
  { name: 'canvas (фон)', value: '#F5F5F6', text: '#1B1C21' },
  { name: 'muted (текст)', value: '#55565E' },
]

interface InvitationRow {
  id: number
  candidate: string
  category: string
  salaryFrom: number
  salaryTo: number
  status: InvitationStatus
  sentAt: string
}

const rows: InvitationRow[] = [
  { id: 1, candidate: 'A7F2', category: 'backend:middle', salaryFrom: 250000, salaryTo: 350000, status: 'sent', sentAt: '2026-10-05' },
  { id: 2, candidate: '3C19', category: 'frontend:senior', salaryFrom: 380000, salaryTo: 450000, status: 'accepted', sentAt: '2026-10-01' },
  { id: 3, candidate: 'B04E', category: 'data_ml:junior', salaryFrom: 140000, salaryTo: 180000, status: 'declined', sentAt: '2026-09-28' },
  { id: 4, candidate: '91DD', category: 'devops:middle', salaryFrom: 260000, salaryTo: 320000, status: 'viewed', sentAt: '2026-10-04' },
  { id: 5, candidate: '5A6B', category: 'qa:intern', salaryFrom: 60000, salaryTo: 80000, status: 'expired', sentAt: '2026-09-20' },
]

const columns: TableColumn<InvitationRow>[] = [
  { key: 'candidate', header: 'Кандидат', sortable: true, render: (r) => <Pseudonym code={r.candidate} size="sm" /> },
  { key: 'category', header: 'Категория', sortable: true, render: (r) => categoryLabel(r.category), hideOnMobile: true },
  {
    key: 'salary',
    header: 'Вилка',
    sortable: true,
    sortValue: (r) => r.salaryFrom,
    render: (r) => <SalaryRange from={r.salaryFrom} to={r.salaryTo} size="sm" />,
  },
  { key: 'status', header: 'Статус', render: (r) => <StatusPill status={r.status} /> },
  { key: 'sentAt', header: 'Отправлено', sortable: true, align: 'right', hideOnMobile: true, render: (r) => new Date(r.sentAt).toLocaleDateString('ru-RU') },
]

const sections = [
  ['brand', 'Бренд ФСП'],
  ['colors', 'Цвета'],
  ['type', 'Типографика'],
  ['buttons', 'Кнопки'],
  ['forms', 'Поля ввода'],
  ['choice', 'Выбор'],
  ['tags', 'Теги и статусы'],
  ['cards', 'Карточки и зарплата'],
  ['table', 'Таблица'],
  ['nav', 'Вкладки, шаги, страницы'],
  ['progress', 'Прогресс и счёт'],
  ['overlays', 'Окна и уведомления'],
  ['states', 'Состояния'],
  ['test', 'Таймер'],
] as const

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      <Card>{children}</Card>
    </section>
  )
}

function Row({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <div className="mb-5 last:mb-0">
      {label && <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{label}</p>}
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </div>
  )
}

export default function UiKitPage() {
  const { toast } = useToast()
  const [stack, setStack] = useState<string[]>(['Python', 'PostgreSQL'])
  const [spec, setSpec] = useState('')
  const [agree, setAgree] = useState(true)
  const [hidden, setHidden] = useState(false)
  const [grade, setGrade] = useState<string | null>('middle')
  const [role, setRole] = useState<string | null>('candidate')
  const [chips, setChips] = useState<string[]>(['fsp'])
  const [tab, setTab] = useState('all')
  const [pill, setPill] = useState('table')
  const [step, setStep] = useState(2)
  const [page, setPage] = useState(3)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [loadingBtn, setLoadingBtn] = useState(false)
  const [timerKey, setTimerKey] = useState(0)

  const toggleChip = (c: string) => setChips((v) => (v.includes(c) ? v.filter((x) => x !== c) : [...v, c]))

  return (
    <div className="py-4">
      <PageHeader
        title="UI-кит"
        description="Компоненты src/shared/ui в фирменных цветах ФСП. Импорт: import { Button } from '@/shared/ui'."
      />
      <div className="grid gap-8 lg:grid-cols-[200px_1fr]">
        <nav aria-label="Разделы UI-кита" className="hidden lg:block">
          <ul className="sticky top-24 space-y-0.5 text-sm">
            {sections.map(([id, label]) => (
              <li key={id}>
                <a href={`#${id}`} className="block rounded-sm px-2 py-1 text-muted hover:bg-primary-soft hover:text-primary">
                  {label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 space-y-10">
          <Section id="brand" title="Бренд ФСП">
            <Row label="Логотип и знак (public/brand)">
              <img src={brandAsset('fsp-logo.svg')} alt="Логотип ФСП" className="h-10 w-auto" width={119} height={40} />
              <img
                src={brandAsset('fsp-logo-full.svg')}
                alt="Федерация спортивного программирования России"
                className="h-8 w-auto max-w-full"
                width={256}
                height={32}
              />
              <FspMark className="size-8" label="Знак ФСП" />
            </Row>
            <Row label="Линейная графика — BrandLines">
              <BrandLines variant="corner" className="h-24 w-auto" />
              <BrandLines variant="wave" className="h-24 w-auto" />
              <BrandLines variant="rule" className="w-48" />
            </Row>
          </Section>

          <Section id="colors" title="Цвета">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-5">
              {colorTokens.map((c) => (
                <div key={c.name} className="overflow-hidden rounded-md border border-line">
                  <div className="flex h-16 items-end p-2 text-xs font-semibold" style={{ background: c.value, color: c.text ?? '#fff' }}>
                    Aa
                  </div>
                  <div className="p-2">
                    <p className="text-[13px] font-semibold">{c.name}</p>
                    <p className="font-mono text-xs text-muted">{c.value}</p>
                  </div>
                </div>
              ))}
            </div>
            <p className="mt-4 text-sm text-muted">
              Главная кнопка — #402FFF с белым текстом (6,8:1). Красный #EC1D35 с белым текстом даёт 4,4:1 (ниже WCAG AA),
              поэтому он только для иконок и полосок, а текст и кнопки «опасно» — #C4122B (6,1:1).
            </p>
          </Section>

          <Section id="type" title="Типографика">
            <p className="font-display text-[28px] font-semibold tracking-[-0.02em]">Заголовок страницы · 28 / JetBrains Mono</p>
            <p className="font-display text-lg font-semibold tracking-[-0.02em]">Заголовок раздела · 18 / JetBrains Mono</p>
            <p className="font-display text-base font-semibold tracking-[-0.02em]">Заголовок карточки · 16 / JetBrains Mono</p>
            <p className="text-[15px]">Основной текст · 15 / Inter Regular. Заголовки h1–h3 получают шрифт бренда автоматически.</p>
            <p className="font-num text-xl font-semibold">250 000 – 350 000 ₽ · θ = 1,24 · 87 баллов</p>
            <p className="text-sm text-muted">Числа — класс font-num (или tabular-nums): JetBrains Mono.</p>
            <p className="text-sm text-muted">Вторичный текст · 14 / muted</p>
            <p className="font-mono text-sm">print(sum(range(10)))  # моноширинный — для задач с кодом</p>
          </Section>

          <Section id="buttons" title="Кнопки">
            <Row label="Варианты">
              <Button>Главное действие</Button>
              <Button variant="secondary">Второстепенное</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger" leftIcon={<Trash2 className="size-4" aria-hidden />}>
                Удалить
              </Button>
            </Row>
            <Row label="Размеры и иконки">
              <Button size="sm" leftIcon={<Plus className="size-4" aria-hidden />}>
                Создать
              </Button>
              <Button size="md" rightIcon={<Send className="size-4" aria-hidden />}>
                Отправить приглашение
              </Button>
              <Button size="lg">Начать тест</Button>
            </Row>
            <Row label="Состояния">
              <Button
                loading={loadingBtn}
                onClick={() => {
                  setLoadingBtn(true)
                  setTimeout(() => setLoadingBtn(false), 1500)
                }}
              >
                {loadingBtn ? 'Сохраняем…' : 'Нажми — загрузка'}
              </Button>
              <Button disabled>Недоступно</Button>
              <Button variant="secondary" disabled>
                Недоступно
              </Button>
            </Row>
          </Section>

          <Section id="forms" title="Поля ввода">
            <div className="grid gap-4 md:grid-cols-2">
              <Input label="Почта" type="email" placeholder="name@example.com" required hint="На неё придёт ссылка подтверждения" />
              <Input label="Зарплата от, ₽" inputMode="numeric" defaultValue="250000" error="Ниже минимальной зарплаты кандидата (280 000 ₽)" />
              <Select
                label="Специализация"
                placeholder="Выберите…"
                options={SPECIALIZATION_OPTIONS}
                value={spec}
                onChange={(e) => setSpec(e.target.value)}
              />
              <Select label="Грейд" options={GRADE_OPTIONS} defaultValue="middle" disabled hint="Смена грейда — не чаще раза в 90 дней" />
              <TagInput
                label="Стек технологий"
                value={stack}
                onChange={setStack}
                options={STACK}
                hint="Enter — добавить, Backspace — убрать последний"
                className="md:col-span-2"
              />
              <Textarea
                label="Опишите, кого ищете"
                placeholder="Нужен backend-разработчик на Python, middle, FastAPI и PostgreSQL обязательно, удалёнка, до 300 тысяч"
                containerClassName="md:col-span-2"
              />
            </div>
          </Section>

          <Section id="choice" title="Выбор">
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                <Checkbox
                  label="Согласен на обработку персональных данных"
                  description="152-ФЗ: без согласия регистрация невозможна"
                  checked={agree}
                  onChange={(e) => setAgree(e.target.checked)}
                />
                <Checkbox label="Неактивный пункт" disabled />
                <Switch
                  label="Не ищу работу"
                  description="Профиль скрыт из подборок, приглашения не приходят"
                  checked={hidden}
                  onChange={setHidden}
                />
              </div>
              <RadioGroup
                label="Грейд для теста"
                value={grade}
                onChange={setGrade}
                options={GRADE_OPTIONS.map((g) => ({ value: g.value, label: g.label }))}
                orientation="horizontal"
              />
            </div>
            <div className="mt-6">
              <RadioGroup
                label="Кто вы?"
                variant="cards"
                orientation="horizontal"
                value={role}
                onChange={setRole}
                options={[
                  { value: 'candidate', label: 'Соискатель', description: 'Ищу работу в IT' },
                  { value: 'recruiter', label: 'Рекрутер', description: 'Ищу специалистов в команду' },
                ]}
              />
            </div>
          </Section>

          <Section id="tags" title="Теги и статусы">
            <Row label="Теги стека">
              <Tag>Python</Tag>
              <Tag>PostgreSQL</Tag>
              <Tag tone="info">Алгоритмы</Tag>
              <Tag tone="neutral" onRemove={() => toast({ title: 'Тег убран' })}>
                Docker
              </Tag>
            </Row>
            <Row label="Чипы-фильтры">
              {[
                ['fsp', 'Есть ФСП'],
                ['remote', 'Удалёнка'],
                ['test', 'Тест пройден'],
              ].map(([id, label]) => (
                <Tag key={id} selected={chips.includes(id)} onClick={() => toggleChip(id)}>
                  {label}
                </Tag>
              ))}
            </Row>
            <Row label="Бейджи">
              <FspVerifiedBadge />
              <Badge tone="accent">Новое</Badge>
              <Badge tone="info">Backend · Middle</Badge>
              <Badge tone="success">Профиль заполнен</Badge>
              <Badge tone="warning">Возможная утечка</Badge>
              <Badge tone="danger">Заблокирован</Badge>
              <Badge>Черновик</Badge>
            </Row>
            <Row label="Статусы приглашений">
              {INVITATION_STATUSES.map((s) => (
                <StatusPill key={s} status={s} />
              ))}
            </Row>
          </Section>

          <Section id="cards" title="Карточки и зарплата">
            <div className="grid gap-4 md:grid-cols-2">
              <Card interactive className="shadow-none">
                <div className="flex items-start justify-between gap-3">
                  <Pseudonym code="A7F2" subtitle="Backend · Middle · Москва" />
                  <FspVerifiedBadge label="ФСП" />
                </div>
                <div className="mt-4 flex flex-wrap gap-1.5">
                  <Tag>Python</Tag>
                  <Tag>FastAPI</Tag>
                  <Tag>PostgreSQL</Tag>
                </div>
                <div className="mt-4 space-y-3">
                  <ScoreBar label="Совпадение стека" value={0.8} contribution={0.32} hint="4 из 5 обязательных технологий" />
                  <ScoreBar label="Результат теста" value={0.65} contribution={0.21} />
                </div>
              </Card>
              <Card className="shadow-none">
                <CardHeader title="Приглашение от «Северный код»" description="Backend-разработчик, команда платежей" actions={<StatusPill status="viewed" />} />
                <SalaryRange label="Зарплата" from={250000} to={350000} size="lg" />
                <div className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
                  <SalaryRange from={180000} size="sm" />
                  <SalaryRange to={120000} size="sm" />
                  <SalaryRange size="sm" />
                </div>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button>Принять</Button>
                  <Button variant="secondary">Отклонить</Button>
                </div>
              </Card>
            </div>
            <Row label="Аватары">
              <Avatar name="Анна Козлова" size="sm" />
              <Avatar name="Дмитрий Орлов" />
              <Avatar name="Мария Белова" size="lg" />
              <Pseudonym id="candidate-42" subtitle="Псевдоним из id" />
            </Row>
          </Section>

          <Section id="table" title="Таблица">
            <p className="mb-3 text-sm text-muted">Клик по заголовку: по возрастанию → по убыванию → без сортировки.</p>
            <Table
              columns={columns}
              rows={rows}
              rowKey={(r) => r.id}
              onRowClick={(r) => toast({ title: `Кандидат #${r.candidate}`, description: categoryLabel(r.category) })}
              caption="Приглашения"
            />
          </Section>

          <Section id="nav" title="Вкладки, шаги, страницы">
            <Row label="Вкладки">
              <Tabs
                className="w-full"
                value={tab}
                onChange={setTab}
                items={[
                  { id: 'all', label: 'Все', count: 24, content: <p className="text-sm text-muted">Все приглашения.</p> },
                  { id: 'active', label: 'Активные', count: 7, content: <p className="text-sm text-muted">Ждут ответа.</p> },
                  { id: 'accepted', label: 'Принятые', count: 3, content: <p className="text-sm text-muted">Контакты открыты.</p> },
                  { id: 'archive', label: 'Архив', disabled: true },
                ]}
              />
            </Row>
            <Row label="Сегментный переключатель">
              <Tabs
                variant="pills"
                value={pill}
                onChange={setPill}
                items={[
                  { id: 'table', label: 'Таблица' },
                  { id: 'kanban', label: 'Канбан' },
                ]}
              />
            </Row>
            <Row label="Мастер онбординга">
              <div className="w-full">
                <Stepper
                  current={step}
                  onStepClick={setStep}
                  steps={[
                    { id: 'profile', label: 'Профиль' },
                    { id: 'survey', label: 'Опрос' },
                    { id: 'grade', label: 'Грейд' },
                    { id: 'test', label: 'Тест' },
                    { id: 'result', label: 'Результат' },
                  ]}
                />
                <div className="mt-4 flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => setStep((s) => Math.max(0, s - 1))}>
                    Назад
                  </Button>
                  <Button size="sm" onClick={() => setStep((s) => Math.min(4, s + 1))}>
                    Далее
                  </Button>
                </div>
              </div>
            </Row>
            <Row label="Фильтры">
              <FilterBar
                className="w-full"
                search={{ value: search, onChange: setSearch, placeholder: 'Поиск по стеку' }}
                activeCount={chips.length + (search ? 1 : 0)}
                onReset={() => {
                  setChips([])
                  setSearch('')
                }}
              >
                <Select options={SPECIALIZATION_OPTIONS} placeholder="Специализация" aria-label="Специализация" containerClassName="sm:w-48" />
                <Select options={GRADE_OPTIONS} placeholder="Грейд" aria-label="Грейд" containerClassName="sm:w-36" />
              </FilterBar>
            </Row>
            <Row label="Пагинация">
              <Pagination page={page} pageCount={12} onChange={setPage} />
            </Row>
          </Section>

          <Section id="progress" title="Прогресс и счёт">
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                <ProgressBar label="Полнота профиля" value={70} />
                <ProgressBar label="Задача" value={7} max={15} showValue="fraction" tone="violet" />
                <ProgressBar label="Квота приглашений" value={18} max={20} showValue="fraction" tone="warning" size="sm" />
              </div>
              <div className="space-y-4">
                <p className="text-sm font-semibold">Почему в подборке</p>
                <ScoreBar label="Совпадение стека" value={0.8} contribution={0.32} hint="Python, FastAPI, PostgreSQL, Docker" />
                <ScoreBar label="Результат теста (θ)" value={0.7} contribution={0.24} hint="Выше среднего по категории" />
                <ScoreBar label="Достижения ФСП" value={0.5} contribution={0.1} hint="2 подтверждённых призовых места" />
                <ScoreBar label="Зарплатные ожидания" value={0.2} contribution={-0.05} hint="Ожидания выше вилки на 10 %" />
              </div>
            </div>
          </Section>

          <Section id="overlays" title="Окна и уведомления">
            <Row>
              <Button onClick={() => setModal(true)}>Открыть модалку</Button>
              <Button variant="secondary" onClick={() => setDrawer(true)}>
                Открыть боковую панель
              </Button>
              <Button variant="secondary" onClick={() => toast({ title: 'Приглашение отправлено', description: 'Кандидат #A7F2 получит уведомление', tone: 'success' })}>
                Toast: успех
              </Button>
              <Button variant="ghost" onClick={() => toast({ title: 'Не удалось сохранить', description: 'Сервер недоступен', tone: 'error' })}>
                Toast: ошибка
              </Button>
              <Tooltip content="Квота — сколько активных приглашений можно держать одновременно">
                <button type="button" className="rounded-full p-1 text-subtle hover:text-fsp-plum" aria-label="Что такое квота">
                  <Info className="size-5" aria-hidden />
                </button>
              </Tooltip>
            </Row>
            <Modal
              open={modal}
              onClose={() => setModal(false)}
              title="Пригласить кандидата #A7F2"
              description="Кандидат увидит компанию, вилку и способ связи"
              footer={
                <>
                  <Button variant="secondary" onClick={() => setModal(false)}>
                    Отмена
                  </Button>
                  <Button
                    onClick={() => {
                      setModal(false)
                      toast({ title: 'Приглашение отправлено', tone: 'success' })
                    }}
                  >
                    Отправить
                  </Button>
                </>
              }
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Зарплата от, ₽" defaultValue="250000" required />
                <Input label="Зарплата до, ₽" defaultValue="350000" required />
                <Textarea label="Описание" containerClassName="sm:col-span-2" rows={3} />
              </div>
              <p className="mt-4 rounded-md bg-info-soft p-3 text-sm text-info">
                В категории Backend · Middle обычно принимают от 240 000 ₽. Вероятность принятия — 64 %.
              </p>
            </Modal>
            <Drawer
              open={drawer}
              onClose={() => setDrawer(false)}
              title="Фильтры"
              footer={<Button onClick={() => setDrawer(false)}>Применить</Button>}
            >
              <div className="space-y-4 p-5">
                <Select label="Специализация" options={SPECIALIZATION_OPTIONS} placeholder="Любая" />
                <Select label="Грейд" options={GRADE_OPTIONS} placeholder="Любой" />
                <Checkbox label="Только с подтверждением ФСП" />
              </div>
            </Drawer>
          </Section>

          <Section id="states" title="Состояния">
            <div className="grid gap-4 md:grid-cols-2">
              <Card padding="none" className="shadow-none">
                <EmptyState
                  title="Приглашений пока нет"
                  description="Когда работодатель пригласит вас, оно появится здесь"
                  action={<Button size="sm" variant="secondary">Заполнить профиль</Button>}
                />
              </Card>
              <Card padding="none" className="shadow-none">
                <ErrorState onRetry={() => toast({ title: 'Повторяем запрос…' })} />
              </Card>
              <SkeletonCard />
              <Card className="shadow-none">
                <Skeleton className="mb-4 h-6 w-1/3" />
                <SkeletonText lines={4} />
              </Card>
            </div>
          </Section>

          <Section id="test" title="Таймер">
            <Row>
              <Timer key={timerKey} durationSec={45} warnAtSec={15} onExpire={() => toast({ title: 'Время вышло', tone: 'warning' })} />
              <Timer durationSec={8} paused />
              <Button variant="secondary" size="sm" onClick={() => setTimerKey((k) => k + 1)} leftIcon={<RotateCw className="size-4" aria-hidden />}>
                Перезапустить
              </Button>
            </Row>
          </Section>
        </div>
      </div>
    </div>
  )
}
