# Flat Finder UI Redesign

Visual refresh of the Flat Finder web UI. Replaces the current "warm cream + teal" design with a sharper, modern aesthetic. CSS rewrite + font swap; no backend or JS logic changes.

## Design Direction

Hybrid of "Modern & Sharp" (bold typography, price overlaid on images, high contrast) and "Minimal & Calm" (generous spacing, warm neutrals, stacked metric display). Both light and dark modes.

## Design Tokens

### Typography

| Role | Font | Weights | Usage |
|------|------|---------|-------|
| Display | Space Grotesk | 600, 700 | Prices, scores, brand, page titles |
| Body | Outfit | 300, 400, 500, 600 | Body text, labels, UI controls |

Google Fonts import replaces current Bricolage Grotesque + DM Sans.

### Colors — Light Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#fafaf8` | Page background |
| `--surface` | `#ffffff` | Cards, toolbar, nav |
| `--surface-hover` | `#fdfcfb` | Card hover |
| `--text` | `#1c1917` | Primary text |
| `--text-muted` | `#78716c` | Secondary text, specs |
| `--text-faint` | `#a8a29e` | Dates, sources, placeholders |
| `--border` | `#f0eeed` | Card borders, dividers |
| `--border-subtle` | `#f5f3f1` | Internal dividers (metrics, footer) |
| `--accent` | `#2563eb` | Links, active states, primary CTA |
| `--accent-hover` | `#1d4ed8` | Hover on accent elements |
| `--accent-light` | `#eff6ff` | Active nav link bg |

### Colors — Dark Mode

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#111110` | Page background |
| `--surface` | `#1a1a1a` | Cards, toolbar, nav |
| `--surface-hover` | `#222220` | Card hover |
| `--text` | `#f5f5f4` | Primary text |
| `--text-muted` | `#8a8580` | Secondary text |
| `--text-faint` | `#6b6560` | Dates, sources |
| `--border` | `#2a2a28` | Card borders |
| `--border-subtle` | `#252523` | Internal dividers |
| `--accent` | `#60a5fa` | Links, active states |
| `--accent-hover` | `#93bbfd` | Hover on accent |
| `--accent-light` | `#1e293b` | Active nav link bg |

### Semantic Colors (both modes)

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--yes` / `--yes-bg` | `#16a34a` / `#dcfce7` | `#4ade80` / `#052e16` | Positive pills |
| `--no` / `--no-bg` | `#dc2626` / `#fee2e2` | `#f87171` / `#350a0a` | Negative pills |
| `--unknown` / `--unknown-bg` | `#6b7280` / `#f3f4f6` | `#71717a` / `#27272a` | Unknown pills |
| `--fav` / `--fav-light` | `#f59e0b` / `#fef3c7` | `#fbbf24` / `#451a03` | Favourite star |
| `--score` / `--score-bg` | `#16a34a` / `#dcfce7` | `#86efac` / `#14532d` | Score badge |

POI palette (`--poi-color-N` / `--poi-bg-N`) carries over from current design unchanged.

### Spacing & Radius

| Token | Value |
|-------|-------|
| `--radius` | `14px` (cards) |
| `--radius-sm` | `8px` (controls, inputs) |
| `--radius-xs` | `5px` (pills, small chips) |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.04)` |
| `--shadow` | `0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.03)` |
| `--shadow-lg` | `0 4px 16px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.03)` |

Dark mode shadows use higher opacity (0.15–0.25 range).

## Component Changes

### Listing Card (feed)

- **Image area**: Price overlaid bottom-left (Space Grotesk, white, text-shadow). Score badge bottom-right (green). Fav button top-right (frosted glass circle). Gradient overlay on bottom half of image.
- **Body**: Address (Outfit 500), date, specs on separate lines. Metrics displayed as stacked pairs (large value on top, small uppercase label below) in a horizontal row — replaces the current inline metric chips. Feature pills (yes/no/unknown) below metrics. Footer with "View details" link and source.
- **Hover**: Subtle translateY(-2px) + shadow-lg. Image scale(1.02).
- **Seen state**: opacity 0.5, hover restores to 0.85 (unchanged).

### Toolbar

- Segmented control: restyled with rounded corners, blue active state.
- Zone pills: same pill shape, blue active state.
- Sort select: restyled to match.
- Weight sliders: same layout, accent-color uses blue.

### Navigation

- Same structure (sticky, brand + links).
- Brand in Space Grotesk 700, links in Outfit 500.
- Active link uses accent-light background + accent color.

### Detail Page

- Same layout (hero image, price, title, address, badges, features, notes, description, map).
- Reskinned with new tokens. Price in Space Grotesk. Action buttons use blue accent.
- No structural changes.

### Settings Page

- Same layout (POI form, POI list, zones section, zone editor).
- Reskinned with new tokens.
- No structural changes.

### Map Page

- Filter buttons restyled to match new design language.
- No structural changes.

## Files Changed

| File | Change |
|------|--------|
| `ui/static/v2.css` | Full rewrite — new tokens, typography, card design |
| `ui/templates/base.html` | Google Fonts import URL updated |
| `ui/templates/feed.html` | Minor: metric display markup change (stacked pairs instead of inline chips) |
| `ui/templates/_macros.html` | Update `poi_metric` macro for stacked layout |
| `ui/templates/map.html` | Restyle inline filter button CSS |

## Files NOT Changed

- All Python (backend, scraper, shared) — untouched
- `ui/static/v2.js` — all interactions, filters, scoring logic untouched
- `ui/templates/detail.html` — no structural changes (CSS handles it)
- `ui/templates/settings.html` — no structural changes
- `ui/static/map.js` — untouched

## Responsive Behavior

Same breakpoints as current (768px, 480px). Grid goes single-column on mobile. Toolbar zones scroll horizontally. Detail hero goes edge-to-edge. No changes to responsive logic — just reskinned.
