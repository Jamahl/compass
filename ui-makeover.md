# Research Studio — UI Makeover Plan

## Design North Star: "Precision Vitality"
Dark, editorial, glassmorphic. Intelligence meets heat of human creation.
Design system: **The Luminescent Grid** (already in Stitch project `16030743847127854109`).
Colors: `#0a0f14` bg · `#8eabff` primary · `#2dfed7` secondary · Manrope/Inter.

---

## Screens to Design in Stitch

- [ ] **Home — Empty State** (oracle search, no run active)
- [ ] **Home — Research Running** (live stage progress + artifact skeleton)
- [ ] **Home — Run Complete** (artifact grid populated, chat unlocked)

---

## Implementation Tasks

### Phase 1 — Tokens & Foundation ✅
- [x] **1.1** Update `apps/web/src/index.css` CSS variables to match Luminescent Grid palette
- [x] **1.2** Install `@fontsource-variable/manrope` + `@fontsource/inter`; swap font-sans to Manrope
- [x] **1.3** Expose surface hierarchy, brand, gradient + glow tokens in `@theme inline`; add `dark` class to `<html>`; add `.text-gradient-brand`, `.bg-gradient-brand`, `.shadow-glow-*`, `.font-label` utilities

### Phase 2 — Layout & Sidebar
- [ ] **2.1** Restyle `RunSidebar.tsx` — dark `surface-container-low` bg, brand wordmark at top, tighter run-history rows with status glow dots, no hard borders
- [ ] **2.2** Update `App.tsx` root layout — remove visible column separators, rely on tonal shift between sidebar / main / right panel

### Phase 3 — Input Panel (the "Oracle")
- [ ] **3.1** Restyle `InputPanel.tsx` central prompt textarea as glassmorphic command input
  - `surface-container-highest` + `backdrop-blur-2xl` + primary glow ring on focus
  - `title-lg` sized text, placeholder in `on-surface-variant`
- [ ] **3.2** Restyle template selector — pill tabs instead of `<select>` dropdown
- [ ] **3.3** Restyle depth slider — thick track, gradient fill, teal secondary glow
- [ ] **3.4** Restyle URLs + context file section — collapsible accordion panels beneath the oracle

### Phase 4 — Output Selector
- [ ] **4.1** Restyle `OutputSelector.tsx` as asymmetric Bento grid
  - Cards: `surface-container-high` → `surface-container-highest` on hover with 2px lift
  - Selected state: primary → secondary gradient border + subtle `primary` bg tint
  - Group headers use `label-sm` Inter in `on-surface-variant`

### Phase 5 — Run Dashboard & Artifacts
- [ ] **5.1** Restyle stage cards in `RunDashboard.tsx` — status pills with glow (blue running, teal done, red error)
- [ ] **5.2** Restyle `ArtifactCard.tsx` — bento tiles, icon prominent, gradient shimmer on pending state
- [ ] **5.3** Restyle `LiveThinking.tsx` event log — monospace `code` blocks on `surface-container-lowest`, collapsible with teal chevron

### Phase 6 — Chat Panel
- [ ] **6.1** Restyle `ChatPanel.tsx` — user bubbles use `primary→secondary` gradient, assistant bubbles `surface-container-high`, input bar glassmorphic
- [ ] **6.2** Blur overlay on locked state — `backdrop-blur-md` with "Complete research to unlock" label centred

### Phase 7 — Polish & QA
- [ ] **7.1** Audit all `border` / `divide` utilities — replace with tonal shifts per "No-Line Rule"
- [ ] **7.2** Audit all shadows — replace with diffused tinted glows
- [ ] **7.3** Smoke-test all existing flows (start run → poll → view artifact → chat) — no regressions
- [ ] **7.4** Test at 1280px, 1440px, 1920px widths

---

## Constraints
- **Do not** change API contracts, route logic, or state management
- **Do not** remove any UI element — only restyle
- **Do not** add new features (no scope creep)
- All changes in `apps/web/src` only
