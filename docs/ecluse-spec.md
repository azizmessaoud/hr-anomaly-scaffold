# Écluse — Landing Page Build

## Problem Statement

The PFA project has a solid architecture and a compelling pitch, but no shareable, polished presentation artifact. A defense committee, potential employer, or open-source audience needs a single portable page that explains what the tool does, why it exists (local-only, human-in-the-loop), how it works (L0–L6 pipeline), and what the vetted design decisions are — without requiring a running backend or build server to view it.

## Solution

Build a single-page React marketing site that presents the project's architecture, stack, and principles as a narrative scroll-through. All content is static mock data. The build inlines every asset into one `dist/index.html` via `vite-plugin-singlefile`, so the deliverable is a single double-clickable file with no server dependency.

## User Stories

1. As a PFA candidate, I want to open the project on any laptop with no setup, so that I can demo it during my defense without worrying about network or build servers.
2. As a RH engineer, I want to instantly see the full L0–L6 pipeline diagram on the landing page, so that I understand which layers touch sensitive data and which don't.
3. As a technical reviewer, I want to see the exact stack per layer (tool + license + cost), so that I can assess whether the project is production-capable or a prototype.
4. As a privacy-conscious stakeholder, I want the page to clearly state that no data leaves the host and no cloud LLM is called, so that I can trust the tool with real employee records.
5. As a human reviewer, I want to see the review-board mockup with the three statuses (🟢/🟡/🔴), so that I understand how a RH manager interacts with the system.
6. As a DevOps reviewer, I want to see the hardware requirements (GPU VRAM for VLM local, CPU fallback notes), so that I can plan deployment infrastructure.
7. As a product owner, I want an explicit "in/out" table aligned to the generic 8-step AI framework, so that I can explain what the project does and deliberately excludes (embeddings, RAG, vector DB).
8. As a contributor, I want the page to list the ADRs already taken (local-only VLM, max-risk combination, Celery chain+chord, reviewer timeout, single-tenancy), so that I understand why the system is built this way.
9. As a first-time visitor, I want a sticky navigation bar with anchor links to each section, so that I can skip directly to the architecture, stack, or pricing.
10. As a decision-maker, I want a pricing/CTA block at the bottom (even if "free / open-source"), so that I know how to adopt the tool.
11. As a screen-reader user, I want semantic headings and alt text on all illustrative elements, so that the page is navigable without a mouse.
12. As a developer with reduced-motion preferences, I want animations (marquee, scramble, reveal) disabled automatically, so that the page doesn't cause discomfort.
13. As a mobile user, I want the page to render without horizontal overflow at ~375 px, so that I can read it on my phone during a commute.
14. As a CI bot, I want `npm run build` to emit a single `dist/index.html` without errors, so that the artifact can be attached to a GitHub Release or dropped into an email.
15. As a PM, I want every animated element (scramble text, count-up stats, reveal on scroll) to degrade gracefully when JS is unavailable, so that the page is still readable in a no-JS environment.
16. As a future maintainer, I want each landing-page section in its own flat component file under `src/components/`, so that I can reorder, replace, or delete sections without touching the others.
17. As a visual designer, I want a consistent tone system (phos/ember/coral/lagoon) mapped to Tailwind classes, so that the color palette stays coherent across all components.
18. As a security auditor, I want the ADRs page to explicitly call out that cloud APIs are blocked from Layer 1 and Layer 2, so that I can verify compliance with RGPD / Loi 09-08.
19. As a stakeholder comparing against competitors, I want a proof/logos marquee (mocked), so that I can claim market validation even before real customer logos exist.
20. As a new contributor, I want a FAQ accordion covering "why not RAG?", "how heavy is the VLM?", and "what SIRH products are supported?", so that I don't have to ask the maintainer the same questions repeatedly.

## Implementation Decisions

- **Single-file production build.** `vite-plugin-singlefile` inlines all JS and CSS into one HTML file at build time. No code-splitting; acceptable because the page has no route-based lazy loading. File is served from `dist/index.html`.
- **Tailwind v4, CSS-first tokens via `@theme`.** Design tokens (colors phos/ember/coral/lagoon, fonts, spacing) live in `index.css` under `@theme`, loaded through `@tailwindcss/vite`. No `tailwind.config.js`. Tone names are canonical vocabulary across all components.
- **All content is static mock data.** A `data.ts` file holds every string, number, array, and fake testimonial. No API calls. This keeps the page fully demoable offline and removes any need for a backend during build or preview.
- **One component per landing-page section.** `App.tsx` composes 11 flat components in `src/components/`: `Navbar`, `Hero`, `Proof`, `Principles`, `Pipeline`, `ReviewBoard`, `Decisions`, `TechBits`, `Voices`, `Faq`, `Outro`. No nested folders — section = file, direct 1:1 mapping between page structure and filesystem.
- **Shared UI primitives in `ui.tsx`.** `Reveal` (scroll-triggered fade-in via `useInView`), `StatusChip`, `RiskGauge` (SVG semi-circle 0–1), `Terminal` (macOS-style chrome wrapper), `SectionHead`, and tone-to-class maps are defined once and reused.
- **Custom hooks in `hooks.ts`.** `useScramble` (hero headline effect), `useCountUp` (stat counters), `useScrollY` (navbar condensed state) — self-contained, not coupled to any specific component.
- **Icons in `icons.tsx`.** All SVG icon components live in one file, exported by name.
- **`cn()` utility.** A `src/utils/cn.ts` file exports a `cn()` function combining `clsx` + `tailwind-merge`; every component imports it for conditional class composition.
- **Vite config must be exactly `vite.config.ts`.** The `@` alias maps to `src/`. Plugins: `react()`, `@tailwindcss/vite`, `viteSingleFile({ injectCSS: true, injectScript: true })`. The previous misnamed `vite_config.ts` must be renamed — Vite silently ignores the underscore variant, causing plugins and alias to never load.
- **Reduced-motion handling.** `prefers-reduced-motion` media query in `index.css` kills marquee, scramble, and reveal animations. Components must respect this at the CSS level, not just at the JS level.
- **Project glossary governs terminology.** `RecStatus` = `"green" | "amber" | "red"`. `Flag` = `{ moteur, detail, score? }`. `Layer` = L0–L6 architecture layer. `cn()` = class merge helper. These names are used consistently across `data.ts` and all components.
- **Domain ADRs are referenced, not re-litigated.** The landing page presents ADR-001 through ADR-009 as settled decisions. Any new ADR about the landing page itself (ADR-001 through ADR-004 in the build plan) is also surfaced in the `Decisions` section.
- **Content placement for `ROADMAP` and `PLANS` data.** `PLANS` (pricing tiers) belongs to `Outro`. `ROADMAP` (S1–S6 weeks) belongs to `Principles` as a "how we got here" strip, since `Principles` is the closest narrative match and `Outro` already owns pricing. If the author disagrees, this is the single decision point to raise.
- **`HARDWARE` data placement.** Logical home is `TechBits`, alongside `STACK`, since the FAQ already answers the same question in prose. No separate hardware section.

## Testing Decisions

- **What makes a good test.** Tests exercise the rendered output and external behavior only — not internal state logic. For a static marketing page, the test surface is: (a) each section renders without throwing, (b) all `href="#..."` anchors resolve to a visible element with a matching `id`, (c) the built `dist/index.html` is a single file with no relative asset URLs, (d) no `console.error` appears during a programmatic scroll-through.
- **Modules to be tested.** At minimum: `data.ts` (shape and completeness), the built artifact (`dist/index.html`), and each component's mount without error.
- **Prior art.** No existing test suite found in the repo. The MVP test approach is a Playwright or Vitest component smoke test per section, plus a build-integrity check. Full E2E (camera, Percy) is out of scope.

## Out of Scope

- The real document-processing pipeline (Layer 1–4: Docling, Ollama, PyOD, FastAPI).
- The Streamlit dashboard and the actual review workflow (approve/reject/flag).
- Real customer logos, real testimonials, or a CMS.
- Authentication, multi-tenancy, or SIRH write adapters.
- Internationalization — page is French-only for the PFA.
- A real pricing backend — `PLANS` is static copy.
- Dark-mode toggle — the tone palette is designed around the current light scheme.

## Further Notes

- The repo is not yet a git repository in the filesystem being explored; all file paths above refer to the working tree only.
- Two open items from the build plan still need human confirmation before `Principles`, `TechBits`, and `Outro` are written: (1) `ROADMAP` placement (Principles vs Outro), (2) whether the 11 missing components exist in another branch or must be authored from scratch.
- Node.js ≥ 20.19 (or ≥ 22.12) is required for Vite 7. Confirm with `node -v` before Phase 0.
