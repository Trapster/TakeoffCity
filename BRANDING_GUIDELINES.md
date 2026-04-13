# TakeoffCity — Branding Guidelines

## Brand Concept

TakeoffCity serves discerning groups — corporate retreat planners, reunion organizers, and milestone celebration planners (age 35–55) — who expect the same quality from their planning tools as they receive from their hotels and airlines. The aesthetic is **warm editorial luxury**: light, authoritative, unhurried. Think Condé Nast Traveler meets a private members' travel concierge. The brand communicates trust, precision, and warmth.

**Primary segments:**
- **Corporate**: Executive teams planning offsites and leadership retreats. Value trustworthiness, precision, and professional presentation.
- **Reunions**: Class and family reunion organizers. Value warmth, accessibility, and a sense of occasion.
- **Celebrations**: Upscale bachelor/bachelorette and milestone birthday groups. Value elegance, discovery, and curated experience.

---

## Positioning: The Feeling, Not the Feature

The brand leads with *how the group will feel*, not what the software does. Every headline, modal title, and CTA should answer the question "how do we want them to feel after this moment?" — not just what action they are performing.

| Functional frame (avoid)         | Feeling frame (prefer)                              |
|----------------------------------|-----------------------------------------------------|
| "Calculate best destination"     | "Find where everyone can arrive with ease"          |
| "Submit your availability"       | "Share your details so we can take care of the rest"|
| "Create a group"                 | "Plan a gathering"                                  |
| "Enter group members' origins"   | "Tell us where your guests are coming from"         |

This also applies to empty states and loading messages — never show bare technical status. Use reassuring, human copy ("Searching connections for your group — just a moment.") over terse system messages.

---

## Segment-Specific Design Notes

### Corporate Retreats
- Lead with precision and transparency: itemized detail, no hidden steps.
- Placeholder copy in forms should reference professional contexts: "Q3 Leadership Retreat", "APAC Summit".
- Avoid leisure-coded language ("escape", "getaway"). Prefer: "offsite", "retreat", "gathering", "summit".
- Trust signal: show clear data provenance ("Live fares · Updated just now") — not vague superlatives.

### Reunions (Family & Class)
- Tone: warm, celebratory, accessible. Avoid jargon and technical precision language.
- Accessibility matters: forms should be large-target, clear-labeled, and unambiguous.
- Copy should acknowledge the occasion: "where the whole family arrives together", "forty years later, one perfect city."
- Empty states and confirmation messages should feel generous, not transactional.

### Celebrations (Bachelor / Bachelorette / Milestone Birthdays)
- Tone: curated, confident, a little elevated — not exclamatory or sales-y.
- Feature the social/shareable angle: sharing the link is a moment, not just a step.
- Lead with outcome imagery in copy: "the weekend your group will still be talking about."
- Avoid overly corporate tone — "occasion", "celebration", and "milestone" work here; "offsite" does not.

---

## Ethical Design Principles

TakeoffCity does not use manipulative patterns. Affluent users who value transparency will abandon platforms that resort to pressure tactics.

**Never use:**
- Urgency alerts ("Only 2 spots left", "3 others are looking")
- Ambiguous pricing or hidden fees discovered at checkout
- Pre-ticked optional checkboxes
- Fake social proof ("Sarah just booked this!")
- Dark-pattern cancellation flows

**Always use:**
- Accurate inventory and status (Pending / Calculated — not animated urgency badges)
- Explicit, clearly-labeled destructive actions — never bury a delete inside a non-obvious flow
- Transparent data use: the sign-up checkbox must clearly state what data is collected and that it can be deleted
- One primary CTA per screen — no competing gold buttons

---

## Logo

**Wordmark**: TakeoffCity (title case, not all-caps)

- Font: **Cormorant 700**, `letter-spacing: 0.06em`, `text-transform: uppercase`
- "Takeoff": Brand text color (`#1C1814`)
- "City": Champagne Gold (`#A8842C`)
- Admin variant: Append an `Admin` tag (sentence case) in DM Mono 400, small pill badge in Surface-2

**Never use**: All-lowercase, icon-only without text, or any color other than the two defined above.

---

## Color Palette

### Backgrounds
| Name       | Hex        | CSS Variable | Usage                          |
|------------|------------|--------------|--------------------------------|
| Linen      | `#F8F5F0`  | `--bg`       | Page background                |
| White      | `#FFFFFF`  | `--surface`  | Card backgrounds               |
| Parchment  | `#F3EFE9`  | `--surface-2`| Inputs, secondary surfaces     |
| Warm Gray  | `#EDE8E1`  | `--surface-3`| Hover states, tertiary fills   |

### Borders
| Name          | Value                    | CSS Variable     | Usage                          |
|---------------|--------------------------|------------------|--------------------------------|
| Border        | `rgba(28,24,20,0.09)`    | `--border`       | Default card and divider lines |
| Border Strong | `rgba(28,24,20,0.16)`    | `--border-strong`| Modal frames, focused states   |

### Text
| Name          | Value                    | CSS Variable   | Usage                          |
|---------------|--------------------------|----------------|--------------------------------|
| Espresso      | `#1C1814`                | `--text`       | Primary text                   |
| Espresso Dim  | `rgba(28,24,20,0.65)`    | `--text-dim`   | Body copy, secondary text      |
| Espresso Muted| `rgba(28,24,20,0.38)`    | `--text-muted` | Labels, placeholders, metadata |

### Accent Colors
| Name              | Hex        | CSS Variable   | Usage                                    |
|-------------------|------------|----------------|------------------------------------------|
| Deep Emerald      | `#0d4c3c`  | `--accent`     | Primary brand color, CTAs, logo "City"   |
| Emerald Dark      | `#0a3d30`  | `--accent-dark`| Button hover states                      |
| Forest Green      | `#2D7D56`  | `--green`      | Success, calculated status               |
| Slate Blue        | `#3A6EA8`  | `--blue`, `--amber` | Score indicators, info stats, feature icon bg |
| Sage              | `#7ba05b`  | —              | Admin chart secondary line only          |
| Danger Red        | `#C0392B`  | `--danger`     | **Destructive actions only** (delete)    |

### Dim Variants
| Variable        | Value                      | Use                              |
|-----------------|----------------------------|----------------------------------|
| `--accent-dim`  | `rgba(13,76,60,0.10)`      | Emerald bg for badges/pills      |
| `--amber-dim`   | `rgba(58,110,168,0.12)`    | Feature icon backgrounds (slate) |
| `--green-dim`   | `rgba(45,125,86,0.10)`     | Success badge backgrounds        |

---

## Typography

### Typefaces

| Role        | Family              | Weights   | Notes                                         |
|-------------|---------------------|-----------|-----------------------------------------------|
| Display     | **Cormorant**       | 600, 700  | All headings, logo. High-contrast serif. Apply `letter-spacing: 0.06em` at small sizes, `-0.01em` at hero scale. |
| Body        | **Jost**            | 300–700   | Body copy, labels, UI text, buttons. Geometric humanist sans — professional and legible. |
| Monospace   | **DM Mono**         | 400, 500  | Data values, dates, codes, section labels, eyebrows. Reserved for purely informational content. |

Google Fonts import (all pages):
```html
<link href="https://fonts.googleapis.com/css2?family=Cormorant:wght@600;700&family=Jost:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
```

### Type Scale

| Element           | Font       | Size                           | Weight | Tracking        |
|-------------------|------------|--------------------------------|--------|-----------------|
| Hero H1           | Cormorant  | `clamp(2.6rem, 6vw, 4.5rem)`  | 700    | `-0.01em`       |
| Page Title        | Cormorant  | `1.9rem`                       | 700    | `0`             |
| Section H2        | Cormorant  | `1.7rem`                       | 700    | `-0.01em`       |
| Card / Modal Title| Cormorant  | `1.2–1.5rem`                   | 700    | `0`             |
| Body              | Jost       | `0.875–1.05rem`                | 400    |                 |
| UI Label          | Jost       | `0.72–0.75rem`                 | 600    | `0.09em`, uppercase |
| Eyebrow           | Jost       | `0.7rem`                       | 600    | `0.14em`, uppercase |
| Section Label     | Jost       | `0.68rem`                      | 600    | `0.12em`, uppercase |
| Data / Stats      | DM Mono    | Varies                         | 400    |                 |
| Monospace pill    | DM Mono    | `0.65–0.78rem`                 | 400    |                 |

---

## Voice and Tone

The brand speaks to people who make considered decisions — they don't need to be sold, they need to be reassured.

| Avoid                        | Prefer                          |
|------------------------------|---------------------------------|
| "distributed", "nomad"       | "your group", "your team"       |
| "High-Density Coordination"  | "Effortless Gathering"          |
| "Data-Driven"                | "Chosen with Precision"         |
| "crunch the numbers"         | "analyze connections and fares" |
| "LIVE" badge                 | static trust signal             |
| "Create a Group"             | "Plan Your Gathering"           |
| "Event Groups"               | "Gatherings"                    |
| "My Event Groups"            | "My Gatherings"                 |
| "Open Group"                 | "View Details"                  |

**Preferred vocabulary**: gathering, occasion, retreat, milestone, connections, curated, arrives, discerning, thoughtfully, precision, effortless.

---

## Components

### Buttons
All buttons use `border-radius: 99px`. Font: Jost 600, `letter-spacing: 0.03em`.

| Variant          | Class               | Style                                        |
|------------------|---------------------|----------------------------------------------|
| Primary          | `.btn-primary`      | Champagne Gold bg, white text               |
| Cancel / Ghost   | `.btn-cancel`       | Parchment bg, border, muted text            |
| Open / Neutral   | `.btn-open`         | Warm Gray bg, Espresso text, border          |
| Danger Outline   | `.btn-danger-outline`| Transparent, danger-red text and border    |
| Danger Solid     | `.btn-danger`       | Danger Red bg, white text — delete only     |

Hover: Primary and danger move `translateY(-1px)`. Transitions: `0.15s ease`.

### Cards
```
background: var(--surface)
border: 1px solid var(--border)
border-radius: 12px
padding: 1.4rem–1.75rem
box-shadow: 0 1px 4px rgba(28,24,20,0.04)
```
On hover: border-color shifts to `rgba(168,132,44,0.25)`, shadow lifts to `0 4px 16px rgba(28,24,20,0.06)`.

### Modals
```
backdrop:  rgba(28,24,20,0.58) + backdrop-filter: blur(6px)
content:   background var(--surface), border 1px var(--border-strong), border-radius 16px
           box-shadow: 0 20px 60px rgba(28,24,20,0.15)
```
Modal titles: Cormorant 700. Danger modal titles: `color: var(--danger)`.

### Form Inputs
```
background: var(--surface-2)      /* parchment */
border: 1px solid var(--border-strong)
border-radius: 8px
font: Jost 0.93rem, color var(--text)
```
Labels: Jost 600, uppercase, `0.09em` tracking, `0.72rem`, `var(--text-muted)`.  
Focus: `border-color: var(--accent)` — champagne gold ring.  
Readonly: `background: var(--surface-3)`, muted text.  
Date picker: native dark icon is correct on light bg; apply `opacity: 0.5` only.

### Status Badges
Pill-shaped, DM Mono 400, uppercase, 0.06em tracking.
- **Pending**: `--accent-dim` bg, `--accent` text, gold border
- **Calculated**: `--green-dim` bg, `--green` text, green border
- **Info**: Blue-dim bg, `--blue` text

### Score Indicators
Slate chip on city cards: `background: var(--amber)` (slate blue `#3A6EA8`), `color: #ffffff`, DM Mono 500. Positioned absolutely top-right.

### Activity Log (`#calculation-log`)
```
background: var(--surface-2)    /* parchment — NOT dark */
color: var(--text-dim)
border: 1px solid var(--border-strong)
font: DM Mono 0.78rem / 1.75
```

### Stat Cards (Admin)
Large numerals in DM Mono 400, `2.25rem`. Color coded:
- Default: Espresso
- Primary metric: Champagne Gold
- Success: Forest Green
- Info: Slate Blue

---

## Layout

- **Max widths**: `1200px` (standard), `1280px` (admin), `1000px` (dashboard), `680px` (settings)
- **Container padding**: `0 1.5rem`
- **Section padding**: `5rem 0`
- **Card gap**: `0.85rem–1.25rem`
- **Breakpoints**: `768px` (mobile), `900px` (admin grid collapse)

---

## Visual Effects

### Hero Gradient Mesh
```css
background:
    radial-gradient(ellipse at 30% 0%, rgba(13,76,60,0.05) 0%, transparent 55%),
    radial-gradient(ellipse at 75% 110%, rgba(13,76,60,0.03) 0%, transparent 50%),
    var(--bg);
```
Barely-there emerald glow on linen. Max opacity: `0.06`. Used only on the landing hero.

### Hero Divider Line
```css
background: linear-gradient(90deg, transparent, rgba(13,76,60,0.28), transparent);
```

### Sticky Header Blur
```css
background: rgba(248,245,240,0.92);
backdrop-filter: blur(20px);
```

### Hover Interactions
- Cards: subtle border shift to gold + `box-shadow` lift
- Buttons: `transform: translateY(-1px)`
- All transitions: `0.15s ease`

**No animated or pulsing elements.** No grain textures. No dark terminal-style output areas.

---

## Admin Chart Colors (Chart.js literals)

```javascript
Groups Created: borderColor '#0d4c3c', bg 'rgba(13,76,60,0.08)'
Feedback:       borderColor '#7ba05b', bg 'rgba(123,160,91,0.08)'
Logins:         borderColor '#3A6EA8', bg 'rgba(58,110,168,0.08)'

grid.color:     'rgba(28,24,20,0.07)'
ticks.color:    'rgba(28,24,20,0.38)'

tooltip.backgroundColor: '#FFFFFF'
tooltip.borderColor:     'rgba(28,24,20,0.12)'
tooltip.titleColor:      '#1C1814'
tooltip.bodyColor:       'rgba(28,24,20,0.65)'
legend.color:            'rgba(28,24,20,0.55)'
```

---

## Do's and Don'ts

### Do
- Use **Cormorant** for all display headings — never Jost at display scale
- Apply `letter-spacing: 0.06em` to Cormorant in the logo and at body/small sizes
- Use **DM Mono** exclusively for data, dates, codes, and monospaced content
- Keep the warm **linen background** (`#F8F5F0`) consistent across all pages
- Reserve **Danger Red** (`#C0392B`) exclusively for irreversible destructive actions
- Write copy that uses "gathering", "occasion", "retreat" — not "event", "group", "data-driven"

### Don't
- Use dark page backgrounds (the brand is light-first, always)
- Use IBM Plex Mono, Syne, Inter, or any system font
- Use Signal Red (`#E03030`) — it is retired from this brand
- Add animated or pulsing UI elements (grain, dots, motion badges)
- Use green-on-black terminal styling for the calculation log
- Style the danger zone red as a brand accent — it is semantic only
- Write "LIVE", "High-Density", "distributed", or tech-coded copy
- Use pill badges as hero trust signals — use a plain eyebrow text line instead (`section-eyebrow` treatment)
- Use urgency dark patterns (countdown timers, fake scarcity, "X people viewing")

---

## Asset Checklist

- [ ] "TakeoffCity" wordmark SVG — Champagne on Linen
- [ ] Favicon / browser icon
- [ ] Open Graph image (1200×630) — editorial style
