# Fightlytics conventions

Fightlytics is MMA fight-video analysis: a dark-only app (Player, Annotate, Accuracy, Training Data QA) plus a marketing landing page that shares its tokens. Components are on `window.Fightlytics.*`.

## Setup
- **Wrap every design in `<AppSurface>`.** The product is dark-only and every component assumes the off-black `--bg-base` page with ink text; on a light host, components render as invisible light-on-white. `padding` (px, default 24; `0` for full-bleed) and `style` are optional.
- Fonts load from Google Fonts through `styles.css`: Archivo (UI), JetBrains Mono (figures), Bebas Neue (wordmark), and Material Symbols Outlined (icons: `<span className="material-symbols-outlined">delete_forever</span>`).
- Components style themselves inline with CSS variables. Your own layout glue should do the same: inline `style` with `var(--token)` plus the shared classes below. There are no utility classes.

## Tokens (`var(--…)`)
| Role | Tokens |
|---|---|
| Surfaces | `--bg-base` page, `--surface-glass` panel, `--surface-glass-2` raised/active, `--surface-inner` tile fill |
| Text | `--text-primary` (ink), `--text-secondary`, `--text-tertiary`, `--text-muted`, `--text-disabled` |
| Borders | `--border-subtle`, `--border-glass`, `--border-strong` |
| Brand/AI | `--accent` (orange), `--accent-hover`, `--accent-on` (text on orange) |
| Corners | `--f-red`, `--f-blue`, `--f-red-dim`, `--f-blue-dim` |
| Fight state | `--state-striking`, `--state-clinch`, `--state-ground` |
| Status | `--warn` (always with an icon or text), `--green-500`, `--red-500` |
| Radii | `--r-ctl` 6px controls, `--r-tile` 8px tiles, `--r-panel` 12px panels |
| Mono | `--mono` |

## Shared classes
- Surfaces: `glass` (panel: surface, border, 12px radius), `inner-tile` (tile inside a panel), `divider` (1px rule on an `<hr>`).
- Type: `font-display` (condensed heavy Archivo for headings, written in sentence case), `font-num` (JetBrains Mono tabular digits for every stat, count and score), `label` (11px muted caption), `eyebrow` (mono section label above a title).
- Controls: `btn-primary` (the one orange action per screen), `btn-ink` (a strong action that isn't the primary), `btn-glass` (outlined secondary), `pill` + `pill active` (segmented filters), `icon-btn`, `kbd` (keyboard key chip), `select` (styled `<select>`).

## Colour rules (these are product rules, not taste)
- **Orange (`--accent`) means the brand, a screen's single primary action, or the AI** (model scores, prediction charts). Selection, focus, playheads and progress use ink (`--text-primary`).
- **Red and blue mean the two corners only, and text never wears a corner colour.** Put a small swatch beside ink text instead (`FighterSelectCard`, `LiveFeed` and `WorstList` show the pattern). Never use red/blue for badges or errors next to fighter data.
- Status is never colour alone: use `StatusBadge`, `VerdictBadge` or `FightPurposeBadge`, which pair an icon with text.
- No rounded-full shapes (despite its name, `.pill` is a 6px segment button), no glow shadows, no gradients on surfaces. Controls use a 6px radius, tiles 8px, panels 12px.

## Where the truth lives
`styles.css`, then `_ds_bundle.css`, define every token and class above; read it before styling. Each component's API is in `components/<group>/<Name>/<Name>.d.ts`, with usage in `<Name>.prompt.md`. Event-shaped props (`LiveFeed.events`) take `fight_events` rows: `action` strings such as `jab`, `cross`, `left_hook`, `calf_kick`, `takedown_attempt`, `knockdown` or `state_clinch`, and `corner` 0 = red, 1 = blue. Frames are 1-based at the fight's integer `fps`.

## Example
```jsx
const { AppSurface, MiniStat, FightPurposeBadge, LiveFeed } = window.Fightlytics;

<AppSurface padding={28}>
  <div className="eyebrow">Player</div>
  <h2 className="font-display" style={{ fontSize: 34, margin: '6px 0 16px' }}>Adesanya vs. Pereira</h2>
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16 }}>
    <div className="glass" style={{ padding: 18, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
      <MiniStat value={54} label="Strikes landed" />
      <MiniStat value="62%" label="Head share" />
      <FightPurposeBadge purpose="ai_labeled" />
    </div>
    <div style={{ height: 480 }}>
      <LiveFeed events={events} currentFrame={720} fps={30} onSeek={() => {}} redName="Adesanya" blueName="Pereira" />
    </div>
  </div>
</AppSurface>
```
