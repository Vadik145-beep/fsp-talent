import type { HttpHandler } from 'msw'
import { adminHandlers } from './admin'
import { candidateHandlers } from './candidate'
import { commonHandlers } from './common'
import { publicHandlers } from './public'
import { recruiterHandlers } from './recruiter'

/** Все хендлеры. Этот файл в волне 1 не правится — каждая роль пишет в свой файл. */
export const handlers: HttpHandler[] = [
  ...commonHandlers,
  ...publicHandlers,
  ...candidateHandlers,
  ...recruiterHandlers,
  ...adminHandlers,
]
