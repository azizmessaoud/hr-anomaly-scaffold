# Écluse — Landing Page Build Plan

> **A note on how this was produced, before you hand it to an agent:**
> You asked for this via `opencode /grill-with-docs`. Two things worth being upfront about:
> 1. This chat interface doesn't have OpenCode installed, and the `/grill-with-docs` skill on file here just points to a `/domain-modeling` command that isn't available in this environment — so I couldn't literally *run* your usual workflow.
> 2. I built this document in that workflow's spirit instead: a glossary, ADRs, an explicit "grilling" section listing what's still unresolved, then a phased plan. Feed this file to OpenCode (or Claude Code) as project context and it can execute from here — or run it back through your actual `/grill-with-docs` command there to interrogate it further.
>
> One practical heads-up if you do use OpenCode for the execution: as of January 2026, Anthropic-hosted Claude models were blocked from being called through OpenCode's provider layer. If your OpenCode setup expects a Claude backend, you'll need to point it at another provider (GPT, Gemini, or a local Ollama model) or run the execution through Claude Code / Claude Desktop instead. Worth double-checking your provider config before you start.

---

## 1. Scope

Build the **Écluse** marketing/pitch landing page — a single-page React site presenting your PFA project (an open-source, self-hosted "firewall" for HR documents). This is the *showcase* front-end: all content is mocked/static (`data.ts`), it does not call your real backend (FastAPI/Celery/PyOD/etc.). Output is a single portable `dist/index.html` file (via `vite-plugin-singlefile`) — no server required to view or hand in.

Out of scope: the actual document-processing pipeline (OCR, PyOD, Streamlit dashboard) — that's a separate project already covered in your architecture diagrams.

---

## 2. Glossary

| Term | Meaning in this codebase |
|---|---|
| `HRRecord` | Canonical shape of one extracted HR document (id, nom, poste, salaire, confiance, risk, status, flags…) — defined in `data.ts`, mirrors the Pydantic model on the backend |
| `RecStatus` | `"green" \| "amber" \| "red"` — the three review verdicts (validé / revue requise / rejeté) |
| `Flag` | One anomaly explanation attached to a record (`moteur`, `detail`, optional `score`) |
| `Layer` | One of the L0–L6 architecture layers (Sécurité, Ingestion, Extraction, Validation, Anomalies, API, Revue) |
| `Tone` | Visual color category (`phos` = green, `ember` = amber, `coral` = red, `lagoon` = teal) — maps to Tailwind classes in `ui.tsx` |
| `Reveal` | Shared scroll-triggered fade-in wrapper (`ui.tsx`, powered by `useInView` in `hooks.ts`) |
| `StatusChip` | Small colored pill showing a `RecStatus` |
| `RiskGauge` | SVG semi-circle gauge rendering a 0–1 risk score |
| `Terminal` | Fake macOS-style terminal window chrome, used to frame code/log snippets |
| `cn()` | Utility combining `clsx` + `tailwind-merge` so conditional Tailwind classes don't collide — **not yet created** |
| singlefile build | `vite-plugin-singlefile` inlines all JS/CSS into one HTML file at build time |
| Scramble text | Hero headline effect cycling glyphs before settling on real text (`useScramble`) |

---

## 3. Current State Audit

### Present (uploaded, verified on disk)
`index.html`, `package.json`, `package-lock.json`, `tsconfig.json`, `main.tsx`, `App.tsx`, `index.css`, `data.ts`, `hooks.ts`, `icons.tsx`, `ui.tsx`, `vite_config.ts` (misnamed, see below)

### Missing — blocks the build right now

| Missing file | Imported by | Why it's needed |
|---|---|---|
| `src/utils/cn.ts` | `ui.tsx` | Class-merge helper; trivial, given below |
| `src/components/Navbar.tsx` | `App.tsx` | Top nav |
| `src/components/Hero.tsx` | `App.tsx` | Landing headline + animated demo console |
| `src/components/Proof.tsx` | `App.tsx` | Logo/name marquee |
| `src/components/Principles.tsx` | `App.tsx` | Manifesto / "why local-only" intro |
| `src/components/Pipeline.tsx` | `App.tsx` | Full L0–L6 architecture breakdown |
| `src/components/ReviewBoard.tsx` | `App.tsx` | Interactive review-table mockup |
| `src/components/Decisions.tsx` | `App.tsx` | In/out framework alignment table |
| `src/components/TechBits.tsx` | `App.tsx` | Stack table + hardware requirements |
| `src/components/Voices.tsx` | `App.tsx` | Testimonial cards |
| `src/components/Faq.tsx` | `App.tsx` | FAQ accordion |
| `src/components/Outro.tsx` | `App.tsx` | Pricing + final CTA |

### One rename required
`vite_config.ts` → **`vite.config.ts`**. Vite only auto-detects this exact filename; with the underscore it's just an inert file and the plugins (`react()`, `tailwindcss()`, `viteSingleFile()`, the `@` alias) silently never load.

---

## 4. Grilling — open questions to resolve before (or while) building

These are inferences from `data.ts` and `App.tsx`'s import order — confirm them, don't just assume:

1. **`PLANS` (pricing) and `ROADMAP` (S1–S6 weeks) aren't obviously owned by any of the 10 imported section components.** Best guess: `PLANS` → rendered inside `Outro` (it sits outside `<main>` in `App.tsx`, which fits a closing pricing+CTA block; also explains the `#tarifs` nav anchor that otherwise points nowhere). `ROADMAP` likely belongs in `Principles` as a "how we got here" strip, or gets folded into `Pipeline`. **Decide which, or it stays dead data.**
2. **`HARDWARE`** (GPU/CPU notes) — logical home is `TechBits`, next to `STACK`, since the FAQ already answers the same question in prose. Confirm.
3. **`Principles` has no nav anchor** in `NAV_LINKS`, unlike every other main section. Intentional (a scroll-past manifesto, not a jump target) or an oversight?
4. **Do the 11 missing components already exist somewhere** (another branch, a previous export, a different Claude/OpenCode session) — or do they need to be written from scratch against the specs in Section 6? This changes whether Phase 2 below is "locate and drop in" or "author."
5. **Node version on your machine** — Vite 7 needs Node 20.19+ or 22.12+. Confirm with `node -v` before anything else; a corporate-image laptop sometimes ships an older pinned LTS.

---

## 5. Architecture Decision Records

**ADR-001 — Single-file production build**
- *Decision:* Use `vite-plugin-singlefile` so `npm run build` emits one `dist/index.html`.
- *Why:* Deliverable for a PFA defense needs to be viewable with zero setup — double-click or email it, no server, no broken relative asset paths.
- *Trade-off:* No code-splitting; fine at this page's size (single page, no route-based lazy loading needed).

**ADR-002 — Tailwind v4 via `@theme`, no `tailwind.config.js`**
- *Decision:* Color/font tokens live in `index.css` under `@theme`, loaded through `@tailwindcss/vite`.
- *Why:* Tailwind v4's CSS-first config removes a whole file class and keeps design tokens co-located with the styles that use them.

**ADR-003 — All content is static mock data, no API calls**
- *Decision:* `data.ts` holds every string, number, and fake testimonial the page shows.
- *Why:* This is a pitch page, not the working app; there is nothing to fetch. Keeps the whole thing buildable/demoable offline, on a laptop with no backend running.

**ADR-004 — One component per landing-page section, section = one file**
- *Decision:* `App.tsx` composes 11 flat components in `src/components/`, no nested folders per section.
- *Why:* Matches page structure 1:1; easy to reorder, easy to find, no premature abstraction for a page this size.

---

## 6. Component specs (in recommended build order)

Build in this order — each one is independently testable, and later ones reuse patterns from earlier ones.

| # | Component | Reads from `data.ts` | Reuses from `ui.tsx` / `hooks.ts` / `icons.tsx` | What it renders |
|---|---|---|---|---|
| 0 | `utils/cn.ts` | — | — | The merge helper (below) |
| 1 | `Navbar` | `NAV_LINKS` | `useScrollY`, `LogoMark` | Sticky top bar, anchor links, condensed style once scrolled |
| 2 | `Hero` | `CONSOLE_SCENARIOS`, `HERO_STATS` | `useScramble`, `useCountUp`, `Terminal`, `StatusChip` | Headline + animated fake-console demo cycling the two scenarios, stat counters |
| 3 | `Proof` | `PROOF_NAMES` | `.marquee` / `.marquee-track` CSS classes already in `index.css` | Infinite-scroll strip of client names |
| 4 | `Principles` | (manifesto copy; optionally `ROADMAP`) | `Reveal`, `SectionHead` | Short "why local-only / why not RAG" positioning section |
| 5 | `Pipeline` | `LAYERS` | `Reveal`, `SectionHead`, `TONE_*` maps, `Terminal` (for `code` blocks), `IconLayers` | Full L0–L6 cards: lead text, bullet points, tool chips, optional code snippet |
| 6 | `ReviewBoard` | `INITIAL_RECORDS`, `STATUS_LABEL` | `StatusChip`, `RiskGauge`, `Terminal` | Table/board of records with status, risk gauge, expandable flags |
| 7 | `Decisions` | `DECISIONS` | `IconCheck`, `IconX`, `Reveal` | Two-column in/out list against the generic "8-step AI framework" |
| 8 | `TechBits` | `STACK`, `HARDWARE` | `IconServer`, `IconCpu`, `Terminal` (for the `mono` command lines) | Stack table + hardware requirement callouts |
| 9 | `Voices` | `TESTIMONIALS` | `IconQuote`, `IconStar`, `Reveal` | Testimonial cards |
| 10 | `Faq` | `FAQS` | `IconChevronDown`, `Reveal` | Accordion |
| 11 | `Outro` | `PLANS` (+ `ROADMAP`?) | `btn-primary`, `card` classes | Pricing tiers + final CTA, rendered outside `<main>` in `App.tsx` |

**`utils/cn.ts` (write this first, everything else compiles against it):**
```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

---

## 7. Phased task list

### Phase 0 — Environment
- [ ] `node -v` → confirm ≥ 20.19 or ≥ 22.12; update via nodejs.org LTS installer if not (works without admin rights on most corporate Windows images)
- [ ] If behind a corporate proxy and `npm install` hangs: `npm config set proxy http://<proxy>:<port>` and `npm config set https-proxy http://<proxy>:<port>`

### Phase 1 — Repo hygiene
- [ ] Rename `vite_config.ts` → `vite.config.ts`
- [ ] Confirm folder layout matches Section 3's tree
- [ ] `npm install`
- [ ] `npm run dev` — expect a **compile error** at this point (missing components) — that's expected, not a regression

### Phase 2 — Utility layer
- [ ] Create `src/utils/cn.ts` (Section 6)
- [ ] Resolve Open Question #4 (locate vs. author the 11 components)

### Phase 3 — Components, in the order from Section 6's table
For each component:
- [ ] Import only what it needs from `data.ts` / `ui.tsx` / `hooks.ts` / `icons.tsx`
- [ ] Wrap section-level reveal animations in `<Reveal>`
- [ ] Confirm it renders with no console errors before moving to the next
- [ ] Check against Section 4's open questions where relevant (`Principles`, `TechBits`, `Outro`)

### Phase 4 — Integration pass
- [ ] Full scroll-through at desktop width — check `ScrollProgress` bar in `App.tsx` tracks correctly
- [ ] Resize to mobile width (~375px) — nothing overflows horizontally
- [ ] Toggle OS-level "reduce motion" — confirm `prefers-reduced-motion` CSS block in `index.css` actually kills the marquee/scramble/reveal animations (test this explicitly, it's easy to break silently)
- [ ] Every `href="#..."` in `NAV_LINKS` scrolls to a real section id

### Phase 5 — Production build
- [ ] `npm run build`
- [ ] `npm run preview` — open the served build, re-check Phase 4's list against the built version (not just dev mode)
- [ ] Confirm `dist/index.html` opens standalone (file:// URL, no dev server running) — this is the actual deliverable

---

## 8. Definition of done

- [ ] `npm run build` completes with zero errors
- [ ] `dist/index.html` opens directly in a browser with no running server and looks correct
- [ ] No `console.error` in dev tools on load or scroll-through
- [ ] All 6 `NAV_LINKS` anchors resolve to a visible section
- [ ] Reduced-motion is honored
- [ ] Open Questions in Section 4 are explicitly answered (even if the answer is "leave as dead data for now")

---

## 9. Handoff note for the agent executing this

If you're feeding this file into OpenCode's `build` agent (or Claude Code): start at Phase 0, don't skip to Phase 3 — half the "bugs" you'd otherwise chase are actually Phase 1's rename issue. Re-run Section 4's open questions as an actual interactive interview with the person before writing `Principles`, `TechBits`, or `Outro`, since those three are the only components where the data-to-component mapping isn't a clean 1:1.
