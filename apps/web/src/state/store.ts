import { create } from 'zustand'
import type { RunState } from '@/api/client'

interface StoreShape {
  currentRunId: string | null
  runState: RunState | null
  setCurrentRun: (id: string | null) => void
  setRunState: (state: RunState | null) => void
  reset: () => void
}

export const useStore = create<StoreShape>((set) => ({
  currentRunId: null,
  runState: null,
  setCurrentRun: (id) => set({ currentRunId: id }),
  setRunState: (state) => set({ runState: state }),
  reset: () => set({ currentRunId: null, runState: null }),
}))
