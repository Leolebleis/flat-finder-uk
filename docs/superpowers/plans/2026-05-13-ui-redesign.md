# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current warm-cream-teal UI with a modern sharp/calm hybrid — new typography (Space Grotesk + Outfit), blue accent, warm neutrals, proper dark mode, stacked metric display.

**Architecture:** Pure CSS rewrite + font swap + one template markup change (feed metrics). All JS interactions untouched. The redesign is purely visual — no backend, no new features.

**Tech Stack:** CSS custom properties, Google Fonts, Jinja2 templates

**Spec:** `docs/2026-05-13-ui-redesign-design.md`

---

## JS-Dependent CSS Classes (DO NOT RENAME)

The JavaScript in `ui/static/v2.js` and `ui/templates/settings.html` references these class names directly. They must remain identical:

`listing-card`, `listing-card--seen`, `listing-card--hidden`, `listing-card__fav--active`, `btn-seen--active`, `btn-action--active`, `btn-action--fav-active`, `seg-control__btn--active`, `poi-weight-slider`, `listing-grid`, `metric--score`, `pill`, `pill--yes`, `pill--no`, `pill--unknown`, `pill--overridden`, `settings__poi`, `settings__zone`, `settings__empty`

---

## Task 1: Update Google Fonts import in base.html

**Files:**
- Modify: `ui/templates/base.html:9-10`

- [ ] **Step 1: Replace the font imports**

Change the Google Fonts `<link>` tags in `base.html`. Replace Bricolage Grotesque + DM Sans with Space Grotesk + Outfit.

```html
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
```

Replace lines 9-10 (the two `preconnect` links and the `css2` link on line 10) with the three lines above. The preconnect lines stay the same; only the `href` on the font CSS link changes.

- [ ] **Step 2: Verify the template renders**

Run: `cd ui && python -c "from jinja2 import Environment, FileSystemLoader; env = Environment(loader=FileSystemLoader('templates')); t = env.get_template('base.html'); print('OK')"`

Expected: `OK` (no Jinja parse errors)

- [ ] **Step 3: Commit**

```bash
git add ui/templates/base.html
git commit -m "style: swap fonts to Space Grotesk + Outfit"
```

---

## Task 2: Rewrite CSS design tokens and base styles

**Files:**
- Modify: `ui/static/v2.css` (full rewrite of lines 1-130 approx — tokens, dark mode tokens, base styles)

This task rewrites the `:root` tokens, dark mode overrides, and base/reset styles. Everything from the top of the file down to (but not including) the `.nav` section.

- [ ] **Step 1: Replace root tokens and base styles**

Replace everything from the top of `v2.css` down to `/* --- Nav --- */` (lines 1-131) with:

```css
/* Flat Finder v3 — Redesign */

/* --- Reset --- */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* --- Tokens --- */
:root {
  --font-display: "Space Grotesk", system-ui, sans-serif;
  --font-body: "Outfit", system-ui, sans-serif;

  --bg: #fafaf8;
  --surface: #ffffff;
  --surface-hover: #fdfcfb;
  --text: #1c1917;
  --text-muted: #78716c;
  --text-faint: #a8a29e;
  --border: #f0eeed;
  --border-subtle: #f5f3f1;

  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-light: #eff6ff;

  --fav: #f59e0b;
  --fav-light: #fef3c7;

  --yes: #16a34a;
  --yes-bg: #dcfce7;
  --no: #dc2626;
  --no-bg: #fee2e2;
  --unknown: #6b7280;
  --unknown-bg: #f3f4f6;

  --score: #16a34a;
  --score-bg: #dcfce7;

  /* POI palette */
  --poi-color-0: #1d4ed8; --poi-bg-0: #dbeafe;
  --poi-color-1: #c2410c; --poi-bg-1: #ffedd5;
  --poi-color-2: #7c3aed; --poi-bg-2: #ede9fe;
  --poi-color-3: #0f766e; --poi-bg-3: #ccfbf1;
  --poi-color-4: #be123c; --poi-bg-4: #ffe4e6;
  --poi-color-5: #b45309; --poi-bg-5: #fef3c7;
  --poi-color-6: #047857; --poi-bg-6: #d1fae5;
  --poi-color-7: #475569; --poi-bg-7: #f1f5f9;

  --radius: 14px;
  --radius-sm: 8px;
  --radius-xs: 5px;
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
  --shadow: 0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03);
  --shadow-lg: 0 4px 16px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.03);
  --transition: 0.2s ease;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111110;
    --surface: #1a1a1a;
    --surface-hover: #222220;
    --text: #f5f5f4;
    --text-muted: #8a8580;
    --text-faint: #6b6560;
    --border: #2a2a28;
    --border-subtle: #252523;

    --accent: #60a5fa;
    --accent-hover: #93bbfd;
    --accent-light: #1e293b;

    --fav-light: #451a03;

    --yes: #4ade80;
    --yes-bg: #052e16;
    --no: #f87171;
    --no-bg: #350a0a;
    --unknown: #71717a;
    --unknown-bg: #27272a;

    --score: #86efac;
    --score-bg: #14532d;

    --poi-color-0: #93c5fd; --poi-bg-0: #172554;
    --poi-color-1: #fdba74; --poi-bg-1: #431407;
    --poi-color-2: #c4b5fd; --poi-bg-2: #2e1065;
    --poi-color-3: #2dd4bf; --poi-bg-3: #042f2e;
    --poi-color-4: #fda4af; --poi-bg-4: #4c0519;
    --poi-color-5: #fcd34d; --poi-bg-5: #451a03;
    --poi-color-6: #34d399; --poi-bg-6: #064e3b;
    --poi-color-7: #94a3b8; --poi-bg-7: #1e293b;

    --shadow-sm: 0 1px 2px rgba(0,0,0,0.2);
    --shadow: 0 1px 3px rgba(0,0,0,0.2), 0 4px 12px rgba(0,0,0,0.15);
    --shadow-lg: 0 4px 16px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15);
  }

  .listing-card__img { opacity: 0.9; }
  .detail__img { opacity: 0.92; }
  .sort-select {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%236b6560' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  }
}

/* --- Base --- */
html {
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  font-family: var(--font-body);
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
```

- [ ] **Step 2: Verify CSS parses**

Open the file in a browser or run a quick check — the rest of the CSS (nav, toolbar, cards, etc.) should still reference the same token names so nothing breaks yet.

- [ ] **Step 3: Commit**

```bash
git add ui/static/v2.css
git commit -m "style: rewrite CSS tokens — new palette, typography, radii"
```

---

## Task 3: Rewrite nav and toolbar CSS

**Files:**
- Modify: `ui/static/v2.css` (nav + toolbar sections, approx lines 133-298 in the original)

- [ ] **Step 1: Replace nav and toolbar CSS**

Replace the `/* --- Nav --- */` section through the end of `/* --- Main layout --- */` with:

```css
/* --- Nav --- */
.nav {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav__inner {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 1.5rem;
  display: flex;
  align-items: center;
  height: 56px;
  gap: 2rem;
}

.nav__brand {
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 1.15rem;
  color: var(--text);
  letter-spacing: -0.02em;
}
.nav__brand:hover { text-decoration: none; color: var(--accent); }

.nav__links { display: flex; gap: 0.25rem; }

.nav__link {
  display: block;
  padding: 0.45rem 0.85rem;
  border-radius: var(--radius-xs);
  color: var(--text-muted);
  font-size: 0.875rem;
  font-weight: 500;
  transition: background var(--transition), color var(--transition);
}
.nav__link:hover { background: var(--bg); color: var(--text); text-decoration: none; }
.nav__link--active { color: var(--accent); background: var(--accent-light); }

/* --- Toolbar (filter bar) --- */
.toolbar {
  position: sticky;
  top: 56px;
  z-index: 90;
  background: var(--bg);
  padding: 0.75rem 0;
  max-width: 1280px;
  margin: 0 auto;
}

.toolbar__row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding: 0 1.5rem;
}

/* Segmented control */
.seg-control {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  flex-shrink: 0;
}

.seg-control__btn {
  padding: 0.4rem 0.85rem;
  border: none;
  border-right: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
}
.seg-control__btn:last-child { border-right: none; }
.seg-control__btn:hover { color: var(--text); background: var(--surface-hover); }
.seg-control__btn--active {
  background: var(--accent);
  color: #fff;
}
.seg-control__btn--active:hover { background: var(--accent-hover); color: #fff; }

/* Zone pills */
.toolbar__zones { display: flex; gap: 0.4rem; flex-wrap: wrap; }

.zone-pill {
  padding: 0.35rem 0.75rem;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 500;
  transition: all var(--transition);
  white-space: nowrap;
}
.zone-pill:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
.zone-pill--active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.zone-pill--active:hover { color: #fff; text-decoration: none; }

/* Sort */
.sort-select {
  margin-left: auto;
  padding: 0.4rem 2rem 0.4rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-muted);
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6' fill='none'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%2378716c' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.7rem center;
}

/* Weight sliders */
.toolbar__sliders {
  display: flex;
  gap: 1.25rem;
  padding: 0.6rem 1.5rem 0;
}
.toolbar__sliders--hidden { display: none; }

.slider-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.slider-label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-muted);
  white-space: nowrap;
}

.slider {
  width: 100px;
  cursor: pointer;
  accent-color: var(--accent);
}

.slider-val {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-muted);
  min-width: 2.5rem;
  font-variant-numeric: tabular-nums;
}

/* --- Main layout --- */
.main {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 1.5rem 3rem;
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/static/v2.css
git commit -m "style: rewrite nav and toolbar CSS"
```

---

## Task 4: Rewrite listing card CSS with new design

**Files:**
- Modify: `ui/static/v2.css` (listing count, grid, and card sections)

- [ ] **Step 1: Replace listing count, grid, and card CSS**

Replace from `/* --- Listing count --- */` through the end of `.listing-card__notes::placeholder` with:

```css
/* --- Listing count --- */
.listing-count {
  font-size: 0.82rem;
  color: var(--text-faint);
  margin-bottom: 0.75rem;
}

/* --- Listing grid --- */
.listing-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1.25rem;
}

/* --- Card --- */
.listing-card {
  background: var(--surface);
  border-radius: var(--radius);
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition), transform var(--transition);
  animation: cardReveal 0.35s ease-out both;
  animation-delay: calc(var(--reveal-i, 0) * 0.04s);
}

@keyframes cardReveal {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.listing-card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}

.listing-card--seen { opacity: 0.5; }
.listing-card--seen:hover { opacity: 0.85; }
.listing-card--hidden { display: none; }

/* Card media */
.listing-card__media {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 10;
  overflow: hidden;
  background: var(--border-subtle);
}

.listing-card__media::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 55%;
  background: linear-gradient(to top, rgba(0,0,0,0.45), transparent);
  pointer-events: none;
}

.listing-card__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}
.listing-card:hover .listing-card__img { transform: scale(1.02); }

.listing-card__no-img {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  font-size: 0.85rem;
}

/* Favourite overlay */
.listing-card__fav {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: rgba(255,255,255,0.85);
  backdrop-filter: blur(8px);
  color: var(--text-faint);
  font-size: 1.15rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
  line-height: 1;
  z-index: 2;
}
.listing-card__fav:hover { color: var(--fav); transform: scale(1.1); }
.listing-card__fav--active { color: var(--fav); background: var(--fav-light); }

@media (prefers-color-scheme: dark) {
  .listing-card__fav { background: rgba(26,26,26,0.75); }
  .listing-card__fav--active { background: var(--fav-light); }
}

/* Price overlay on image */
.listing-card__price {
  position: absolute;
  bottom: 0.85rem;
  left: 1rem;
  z-index: 2;
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.03em;
  text-shadow: 0 1px 8px rgba(0,0,0,0.3);
}
.listing-card__price small {
  font-weight: 500;
  font-size: 0.55em;
  opacity: 0.85;
}

/* Score overlay */
.listing-card__score {
  position: absolute;
  bottom: 0.85rem;
  right: 0.85rem;
  z-index: 2;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-xs);
  background: var(--score-bg);
  color: var(--score);
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 0.82rem;
  line-height: 1;
}

/* Card body */
.listing-card__body {
  padding: 1.1rem 1.25rem 1.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.listing-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

/* Seen button */
.btn-seen {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1.5px solid var(--border);
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition);
  flex-shrink: 0;
}
.btn-seen:hover { border-color: var(--accent); color: var(--accent); }
.btn-seen--active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.listing-card__address {
  font-size: 0.9rem;
  color: var(--text);
  font-weight: 500;
  line-height: 1.35;
}
.listing-card__address:hover { color: var(--accent); text-decoration: none; }

.listing-card__date {
  font-size: 0.75rem;
  color: var(--text-faint);
}

.listing-card__specs {
  font-size: 0.82rem;
  color: var(--text-muted);
  padding-top: 0.1rem;
}

/* Metrics — stacked value/label pairs */
.listing-card__metrics {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 0.15rem;
}

.metric-stacked {
  display: flex;
  flex-direction: column;
}

.metric-stacked__value {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
}

.metric-stacked__label {
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 500;
  color: var(--text-faint);
}

/* Legacy inline metric (used on detail page badges) */
.metric {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-xs);
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--unknown-bg);
  color: var(--text-muted);
}

.metric--score { background: var(--score-bg); color: var(--score); }

/* Distance metric (inline, feed card) */
.metric--station {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-xs);
  font-size: 0.75rem;
  font-weight: 600;
  background: var(--unknown-bg);
  color: var(--text-muted);
}

/* Feature pills */
.listing-card__features {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding-top: 0.4rem;
}

.pill {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius-xs);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.pill--yes { background: var(--yes-bg); color: var(--yes); }
.pill--no { background: var(--no-bg); color: var(--no); }
.pill--unknown { background: var(--unknown-bg); color: var(--unknown); }
.pill--overridden { border: 1.5px dashed var(--text-faint); }

[data-action="cycle-pill"] {
  cursor: pointer;
  transition: opacity var(--transition);
}
[data-action="cycle-pill"]:hover { opacity: 0.7; }

/* Card footer */
.listing-card__footer {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: auto;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
}

.listing-card__detail-link {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--accent);
}
.listing-card__detail-link:hover { text-decoration: none; color: var(--accent-hover); }

.listing-card__source-link {
  font-size: 0.78rem;
  color: var(--text-faint);
  margin-left: auto;
}
.listing-card__source-link:hover { color: var(--text-muted); }

/* Card notes */
.listing-card__notes {
  width: 100%;
  margin-top: 0.35rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  background: transparent;
  font-family: var(--font-body);
  font-size: 0.8rem;
  color: var(--text);
  resize: vertical;
  transition: border-color var(--transition), background var(--transition);
}
.listing-card__notes:hover {
  border-color: var(--border);
  background: var(--surface-hover);
}
.listing-card__notes:focus {
  outline: none;
  border-color: var(--accent);
  background: var(--surface);
}
.listing-card__notes::placeholder { color: var(--text-faint); }
```

Key changes from old design:
- Card radius is now 14px
- Price moved from card body into image overlay (`position: absolute` on `.listing-card__price`)
- Image gets a gradient overlay via `.listing-card__media::after`
- New `.metric-stacked` / `.metric-stacked__value` / `.metric-stacked__label` classes for stacked metrics
- Old `.metric` class kept for detail page badges
- Card header no longer contains the price (it was moved to the image)

- [ ] **Step 2: Commit**

```bash
git add ui/static/v2.css
git commit -m "style: rewrite listing card CSS — price overlay, stacked metrics"
```

---

## Task 5: Rewrite detail, settings, empty, and responsive CSS

**Files:**
- Modify: `ui/static/v2.css` (everything from `/* --- Detail page --- */` to end of file)

- [ ] **Step 1: Replace detail page through end of file**

Replace from `/* --- Detail page --- */` to the end of the file with:

```css
/* --- Detail page --- */
.detail {
  max-width: 880px;
  margin: 0 auto;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.detail__back {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--accent);
}
.detail__back:hover { text-decoration: none; color: var(--accent-hover); }

.detail__hero {
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--border-subtle);
  margin-bottom: 1.75rem;
}

.detail__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.detail__no-img {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-faint);
  font-size: 1rem;
}

.detail__content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.detail__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
}

.detail__price {
  font-family: var(--font-display);
  font-size: 2rem;
  font-weight: 700;
  color: var(--text);
  letter-spacing: -0.03em;
  line-height: 1.2;
}
.detail__price small {
  font-weight: 500;
  font-size: 0.5em;
  color: var(--text-muted);
}

.detail__title {
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 600;
  color: var(--text);
  margin-top: 0.25rem;
  letter-spacing: -0.01em;
}

.detail__address {
  font-size: 0.95rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

/* Quick actions */
.detail__quick-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.5rem 0.85rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  font-family: var(--font-body);
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
}
.btn-action:hover { border-color: var(--accent); color: var(--accent); text-decoration: none; }
.btn-action--active { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn-action--fav:hover { border-color: var(--fav); color: var(--fav); }
.btn-action--fav-active { border-color: var(--fav); color: var(--fav); background: var(--fav-light); }
.btn-action--primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.btn-action--primary:hover { background: var(--accent-hover); color: #fff; }

/* Detail badges */
.detail__badges {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

/* Detail features */
.detail__label {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.5rem;
}

.detail__label-hint {
  font-family: var(--font-body);
  font-weight: 400;
  font-size: 0.78rem;
  color: var(--text-faint);
}

.detail__pills {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.detail__pills .pill {
  font-size: 0.82rem;
  padding: 0.3rem 0.7rem;
  border-radius: var(--radius-sm);
}

/* Notes */
.notes-input {
  width: 100%;
  padding: 0.65rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-family: var(--font-body);
  font-size: 0.875rem;
  color: var(--text);
  resize: vertical;
  transition: border-color var(--transition);
  min-height: 4.5rem;
}
.notes-input:focus { outline: none; border-color: var(--accent); }
.notes-input::placeholder { color: var(--text-faint); }

/* Description */
.detail__description {
  line-height: 1.75;
  white-space: pre-wrap;
  font-size: 0.9rem;
  color: var(--text-muted);
}

/* Map */
.detail__map {
  width: 100%;
  height: 320px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
}

/* --- Empty state --- */
.empty {
  text-align: center;
  padding: 5rem 1rem;
  color: var(--text-muted);
}
.empty__title {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  color: var(--text);
}
.empty__sub { font-size: 0.9rem; }

/* --- Settings page --- */
.settings {
  max-width: 640px;
  margin: 0 auto;
  animation: fadeIn 0.3s ease-out;
}

.settings__title {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  margin: 1.5rem 0 0.25rem;
}

.settings__desc {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 1.5rem;
}

.settings__form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
  flex-wrap: wrap;
  margin-bottom: 2rem;
}

.settings__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.settings__field label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-muted);
}
.settings__field input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 0.875rem;
}
.settings__field input:focus {
  outline: none;
  border-color: var(--accent);
}
.settings__field--wide { flex: 1; min-width: 200px; }
.settings__field--wide input { width: 100%; }

.settings__list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.settings__poi {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.settings__poi-swatch {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.settings__poi-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.settings__poi-coords {
  font-size: 0.8rem;
  color: var(--text-faint);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.settings__poi-delete {
  border: none;
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: flex;
  transition: all var(--transition);
}
.settings__poi-delete:hover {
  color: var(--no);
  background: var(--no-bg);
}

.settings__empty {
  font-size: 0.875rem;
  color: var(--text-faint);
  text-align: center;
  padding: 2rem;
}

/* --- Settings: Zones --- */
.settings__title--zones {
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid var(--border);
}

.settings__zone-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}

.settings__zone {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.settings__zone-swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  flex-shrink: 0;
}

.settings__zone-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  min-width: 0;
}

.settings__zone-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.settings__zone-meta {
  font-size: 0.75rem;
  color: var(--text-faint);
  font-variant-numeric: tabular-nums;
}

.settings__zone-edit,
.settings__zone-delete {
  border: none;
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: flex;
  transition: all var(--transition);
}
.settings__zone-edit:hover {
  color: var(--accent);
  background: var(--accent-light);
}
.settings__zone-delete:hover {
  color: var(--no);
  background: var(--no-bg);
}

.settings__add-zone {
  margin-top: 1rem;
  margin-bottom: 2rem;
}

/* Zone editor */
.zone-editor {
  margin-top: 1rem;
  margin-bottom: 2rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--surface);
}

.zone-editor__header {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  padding: 1rem;
  flex-wrap: wrap;
}
.zone-editor__header .settings__field {
  flex: 1;
  min-width: 180px;
}

.zone-editor__actions {
  display: flex;
  gap: 0.5rem;
}

.zone-editor__map {
  height: 420px;
  border-top: 1px solid var(--border);
}

.zone-editor__hint {
  padding: 0.6rem 1rem;
  font-size: 0.8rem;
  color: var(--text-faint);
  border-top: 1px solid var(--border);
}

.zone-map-label {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  color: var(--text-faint);
}

/* --- Responsive --- */
@media (max-width: 768px) {
  .nav__inner { padding: 0 1rem; height: 50px; }

  .main { padding: 0 1rem 2rem; }

  .toolbar { top: 50px; }
  .toolbar__row { padding: 0 1rem; gap: 0.5rem; }
  .toolbar__sliders { padding: 0.5rem 1rem 0; flex-wrap: wrap; }

  .toolbar__zones {
    order: 3;
    flex-basis: 100%;
    overflow-x: auto;
    flex-wrap: nowrap;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  .toolbar__zones::-webkit-scrollbar { display: none; }

  .sort-select { order: 2; margin-left: auto; }

  .listing-grid { grid-template-columns: 1fr; gap: 1rem; }

  .listing-card { animation: none; }

  .detail__hero {
    border-radius: 0;
    margin-left: -1rem;
    margin-right: -1rem;
    width: calc(100% + 2rem);
    aspect-ratio: 16 / 10;
  }

  .detail__top { flex-direction: column; gap: 1rem; }
  .detail__quick-actions { justify-content: flex-start; }
  .detail__price { font-size: 1.5rem; }
  .detail__title { font-size: 1.15rem; }
}

@media (max-width: 480px) {
  .seg-control__btn { padding: 0.35rem 0.65rem; font-size: 0.78rem; }
  .listing-card__price { font-size: 1.3rem; }
  .listing-card__body { padding: 0.85rem 1rem 1rem; }
}
```

- [ ] **Step 2: Commit**

```bash
git add ui/static/v2.css
git commit -m "style: rewrite detail, settings, and responsive CSS"
```

---

## Task 6: Update feed.html — move price into image, stacked metrics

**Files:**
- Modify: `ui/templates/feed.html:58-111` (card media and metrics sections)

The card body currently contains the price in `.listing-card__header`. In the new design, price is overlaid on the image. We also change POI metrics from inline chips to stacked value/label pairs.

- [ ] **Step 1: Move price into the media section**

In `feed.html`, find the card media div (starting at `<div class="listing-card__media">`). Add the price overlay inside the media div, after the fav button and before the closing `</div>`:

Replace the entire media block:

```html
        <div class="listing-card__media">
            {% if l.image_url %}
            <img class="listing-card__img" src="{{ l.image_url }}" alt="{{ l.address or 'Listing' }}" loading="lazy">
            {% else %}
            <div class="listing-card__no-img">No image</div>
            {% endif %}

            <button class="listing-card__fav {% if l.favourite %}listing-card__fav--active{% endif %}"
                    data-action="toggle-fav"
                    data-id="{{ l.id }}"
                    data-favourite="{{ 'true' if l.favourite else 'false' }}"
                    aria-label="Favourite">&#9733;</button>

            {% if l.match_score is not none %}
            <span class="listing-card__score metric--score">{{ l.match_score }}</span>
            {% endif %}
        </div>
```

with:

```html
        <div class="listing-card__media">
            {% if l.image_url %}
            <img class="listing-card__img" src="{{ l.image_url }}" alt="{{ l.address or 'Listing' }}" loading="lazy">
            {% else %}
            <div class="listing-card__no-img">No image</div>
            {% endif %}

            <button class="listing-card__fav {% if l.favourite %}listing-card__fav--active{% endif %}"
                    data-action="toggle-fav"
                    data-id="{{ l.id }}"
                    data-favourite="{{ 'true' if l.favourite else 'false' }}"
                    aria-label="Favourite">&#9733;</button>

            <span class="listing-card__price">
                {% if l.price_pcm %}&pound;{{ "{:,}".format(l.price_pcm) }}<small>/mo</small>{% else %}Price TBC{% endif %}
            </span>

            {% if l.match_score is not none %}
            <span class="listing-card__score metric--score">{{ l.match_score }}</span>
            {% endif %}
        </div>
```

- [ ] **Step 2: Remove price from card body header**

The card body header currently has the price and seen button. Replace the header block:

```html
            <div class="listing-card__header">
                <span class="listing-card__price">
                    {% if l.price_pcm %}&pound;{{ "{:,}".format(l.price_pcm) }}<small>/mo</small>{% else %}Price TBC{% endif %}
                </span>
                <button class="btn-seen {% if l.seen %}btn-seen--active{% endif %}"
                        data-action="toggle-seen"
                        data-id="{{ l.id }}"
                        data-seen="{{ 'true' if l.seen else 'false' }}"
                        aria-label="Mark seen"
                        title="{{ 'Seen' if l.seen else 'Mark as seen' }}">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </button>
            </div>
```

with just the seen button (no wrapping header div needed since price is now on the image):

```html
            <div class="listing-card__header">
                <a class="listing-card__address" href="{{ request.url_for('detail_page', listing_id=l.id) }}">{{ l.address or "Address not available" }}</a>
                <button class="btn-seen {% if l.seen %}btn-seen--active{% endif %}"
                        data-action="toggle-seen"
                        data-id="{{ l.id }}"
                        data-seen="{{ 'true' if l.seen else 'false' }}"
                        aria-label="Mark seen"
                        title="{{ 'Seen' if l.seen else 'Mark as seen' }}">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </button>
            </div>
```

And remove the duplicate standalone address link that follows (the old `<a class="listing-card__address"...>` line).

- [ ] **Step 3: Replace POI metrics with stacked layout**

Replace the metrics div:

```html
            <div class="listing-card__metrics">
                {% for poi in pois %}
                {% if poi.id in l.poi_commutes %}{{ poi_metric(l.poi_commutes[poi.id], poi) }}{% endif %}
                {% endfor %}
                {% if l.distance_mi is not none %}
                <span class="metric metric--station">{{ l.distance_mi }} mi from stn</span>
                {% endif %}
            </div>
```

with:

```html
            <div class="listing-card__metrics">
                {% for poi in pois %}
                {% if poi.id in l.poi_commutes %}{{ poi_metric(l.poi_commutes[poi.id], poi) }}{% endif %}
                {% endfor %}
                {% if l.distance_mi is not none %}
                <div class="metric-stacked">
                    <span class="metric-stacked__value">{{ l.distance_mi }}mi</span>
                    <span class="metric-stacked__label">Station</span>
                </div>
                {% endif %}
            </div>
```

- [ ] **Step 4: Commit**

```bash
git add ui/templates/feed.html
git commit -m "style: feed card — price on image, stacked metrics"
```

---

## Task 7: Update _macros.html — stacked POI metric

**Files:**
- Modify: `ui/templates/_macros.html:25-27`

- [ ] **Step 1: Replace the poi_metric macro**

Replace:

```html
{% macro poi_metric(commute_mins, poi) %}
<span class="metric" style="background: var(--poi-bg-{{ poi.color_index % 8 }}); color: var(--poi-color-{{ poi.color_index % 8 }});">{{ commute_mins }} min to {{ poi.name }}</span>
{% endmacro %}
```

with:

```html
{% macro poi_metric(commute_mins, poi) %}
<div class="metric-stacked">
    <span class="metric-stacked__value" style="color: var(--poi-color-{{ poi.color_index % 8 }});">{{ commute_mins }}m</span>
    <span class="metric-stacked__label">{{ poi.name }}</span>
</div>
{% endmacro %}
```

- [ ] **Step 2: Commit**

```bash
git add ui/templates/_macros.html
git commit -m "style: stacked POI metric macro"
```

---

## Task 8: Restyle map page filter buttons

**Files:**
- Modify: `ui/templates/map.html:7-39` (inline `<style>` block)

- [ ] **Step 1: Replace the inline CSS in map.html**

Replace the entire `<style>` block:

```html
<style>
    html, body { margin: 0; padding: 0; height: 100%; }
    #map { width: 100%; height: calc(100vh - 40px); }

    .map-filters {
        position: absolute;
        top: 50px;
        right: 10px;
        z-index: 1000;
        display: flex;
        gap: 4px;
    }
    .map-filters button {
        padding: 6px 12px;
        border: 1px solid #999;
        border-radius: 4px;
        background: #fff;
        cursor: pointer;
        font-size: 13px;
    }
    .map-filters button.active {
        background: #333;
        color: #fff;
        border-color: #333;
    }
    .zone-label {
        background: transparent;
        border: none;
        box-shadow: none;
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        font-weight: 600;
        color: #666;
    }
</style>
```

with:

```html
<style>
    html, body { margin: 0; padding: 0; height: 100%; }
    #map { width: 100%; height: calc(100vh - 40px); }

    .map-filters {
        position: absolute;
        top: 50px;
        right: 10px;
        z-index: 1000;
        display: flex;
        gap: 6px;
    }
    .map-filters button {
        padding: 0.4rem 0.75rem;
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        background: var(--surface);
        color: var(--text-muted);
        cursor: pointer;
        font-family: var(--font-body);
        font-size: 0.82rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .map-filters button:hover {
        border-color: var(--accent);
        color: var(--accent);
    }
    .map-filters button.active {
        background: var(--accent);
        color: #fff;
        border-color: var(--accent);
    }
    .zone-label {
        background: transparent;
        border: none;
        box-shadow: none;
        font-family: var(--font-body);
        font-size: 12px;
        font-weight: 600;
        color: var(--text-faint);
    }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add ui/templates/map.html
git commit -m "style: restyle map filter buttons to match redesign"
```

---

## Task 9: Visual verification and deploy

- [ ] **Step 1: Run linter**

Run: `uv run ruff check ui/`
Expected: No errors (only CSS/HTML changed, but check for any Python import issues)

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_ui.py -v`
Expected: All tests pass (no Python logic changed)

- [ ] **Step 3: Deploy to Pi and verify**

```bash
git push origin main
ssh pi "cd /home/leo/documents/code/raspberrypi/flat-finder && git pull origin main && docker compose up -d --build"
```

Open https://raspberrypi/flat/ and verify:
- Feed page: cards show price on image, stacked metrics, blue accent, correct typography
- Dark mode: toggle system preference and verify dark tokens apply
- Detail page: reskinned with blue accent, Space Grotesk prices
- Settings page: styled with new tokens
- Map page: filter buttons match new design
- Mobile: check on phone — single column, horizontal zone scroll, edge-to-edge detail hero

- [ ] **Step 4: Final commit if any tweaks needed**

```bash
git add -A
git commit -m "style: UI redesign tweaks from visual QA"
```
