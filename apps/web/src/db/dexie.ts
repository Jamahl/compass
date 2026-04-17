import Dexie, { type Table } from 'dexie'

export interface ChatMessageRow {
  id?: number
  runId: string
  role: 'user' | 'assistant'
  content: string
  ts: number
}

class ResearchStudio extends Dexie {
  messages!: Table<ChatMessageRow, number>
  constructor() {
    super('ResearchStudio')
    this.version(1).stores({ messages: '++id, runId, role, ts' })
  }
}

export const db = new ResearchStudio()
