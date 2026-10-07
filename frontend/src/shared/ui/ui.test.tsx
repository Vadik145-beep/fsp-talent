import { useState } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { BrandLines, Button, FspVerifiedBadge, Modal, StatusPill, Table, TagInput, type TableColumn } from '.'
import { INVITATION_STATUSES, INVITATION_STATUS_LABELS } from '@/shared/config/dictionaries'

describe('UI-кит', () => {
  it('Button в состоянии loading заблокирована', async () => {
    const onClick = vi.fn()
    render(
      <Button loading onClick={onClick}>
        Сохранить
      </Button>,
    )
    const btn = screen.getByRole('button', { name: 'Сохранить' })
    expect(btn).toBeDisabled()
    expect(btn).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(btn)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('StatusPill показывает русские подписи всех статусов', () => {
    render(
      <div>
        {INVITATION_STATUSES.map((s) => (
          <StatusPill key={s} status={s} />
        ))}
      </div>,
    )
    for (const s of INVITATION_STATUSES) {
      expect(screen.getByText(INVITATION_STATUS_LABELS[s])).toBeInTheDocument()
    }
    expect(screen.getByText('Отозвано')).toBeInTheDocument()
  })

  it('StatusPill различает статусы не только цветом: у каждого своя иконка', () => {
    const { container } = render(
      <div>
        {INVITATION_STATUSES.map((s) => (
          <StatusPill key={s} status={s} />
        ))}
      </div>,
    )
    const icons = Array.from(container.querySelectorAll('[data-status] svg')).map((svg) => svg.getAttribute('class'))
    expect(icons).toHaveLength(INVITATION_STATUSES.length)
    expect(new Set(icons).size).toBe(INVITATION_STATUSES.length)
  })

  it('FspVerifiedBadge — со знаком ФСП из public/brand; BrandLines декоративные', () => {
    const { container } = render(
      <div>
        <FspVerifiedBadge />
        <BrandLines variant="wave" />
        <BrandLines variant="rule" />
      </div>,
    )
    expect(screen.getByText('Подтверждено ФСП')).toBeInTheDocument()
    expect(container.querySelector('img[src$="brand/fsp-mark.svg"]')).not.toBeNull()
    expect(container.querySelectorAll('[aria-hidden="true"] circle, svg[aria-hidden="true"]').length).toBeGreaterThan(0)
  })

  it('Table сортирует по клику: по возрастанию → по убыванию → исходный порядок', async () => {
    type Row = { id: number; name: string; score: number }
    const rows: Row[] = [
      { id: 1, name: 'Б', score: 2 },
      { id: 2, name: 'А', score: 3 },
      { id: 3, name: 'В', score: 1 },
    ]
    const columns: TableColumn<Row>[] = [
      { key: 'name', header: 'Имя' },
      { key: 'score', header: 'Счёт', sortable: true },
    ]
    render(<Table columns={columns} rows={rows} rowKey={(r) => r.id} />)
    const names = () =>
      screen
        .getAllByRole('row')
        .slice(1)
        .map((tr) => within(tr).getAllByRole('cell')[0].textContent)
    const header = screen.getByRole('button', { name: /Счёт/ })
    expect(names()).toEqual(['Б', 'А', 'В'])
    await userEvent.click(header)
    expect(names()).toEqual(['В', 'Б', 'А'])
    expect(screen.getByRole('columnheader', { name: /Счёт/ })).toHaveAttribute('aria-sort', 'ascending')
    await userEvent.click(header)
    expect(names()).toEqual(['А', 'Б', 'В'])
    await userEvent.click(header)
    expect(names()).toEqual(['Б', 'А', 'В'])
  })

  it('TagInput добавляет по Enter, из подсказок и удаляет Backspace', async () => {
    function Harness() {
      const [v, setV] = useState<string[]>([])
      return <TagInput label="Стек" value={v} onChange={setV} options={['Python', 'PostgreSQL', 'Go']} />
    }
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByRole('combobox', { name: 'Стек' })
    await user.type(input, 'Rust{Enter}')
    expect(screen.getByText('Rust')).toBeInTheDocument()
    await user.type(input, 'post')
    await user.click(screen.getByRole('option', { name: 'PostgreSQL' }))
    expect(screen.getByRole('button', { name: 'Убрать PostgreSQL' })).toBeInTheDocument()
    await user.type(input, '{Backspace}')
    expect(screen.queryByRole('button', { name: 'Убрать PostgreSQL' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Убрать Rust' })).toBeInTheDocument()
  })

  it('Modal закрывается по Escape', async () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="Пригласить">
        <input aria-label="Поле" />
      </Modal>,
    )
    expect(screen.getByRole('dialog', { name: 'Пригласить' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
