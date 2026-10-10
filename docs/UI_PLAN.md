# FROSTGUARD App — UI Plan (AI Handoff)

> Read this before writing any UI code. Latest decision: **Home v3 Big Door** overrides all older home designs.

## 1. App Overview
- Freezer door monitor (ESP32 `esp32-freezer-01` + backend `http://10.44.179.86:8000` + WebSocket live).
- 3 tabs, bottom bar. `Status` is home. Dark theme only.
- Goal: polished, edged, industrial. No AI slop, no text everywhere.

## 2. Navigation
- Bottom bar, 3 tabs: `[Status] [History] [Settings]`.
- Floating bar, active tab = dot + glow. `Status` is default route.
- Header (all screens): glass, left `❄ FROSTGUARD`, right live pill only. No subtitles.

## 3. Design Tokens
```
bg: #070D1A -> #0B1220 gradient
surface: #111C33 / #16213A
border: rgba(34,211,238,0.12)
text-hi: #F1F5F9  text-lo: #8B9BB4
accent cyan: #22D3EE
ok: #22C55E  warn: #F59E0B  danger: #EF4444
fonts: Inter/System + JetBrains Mono for timer only
radius: 8px sharp (hero/door/cards), 999px pills only
```

Global rule: **Screen tint follows state.** Only Status hero glows green/amber/red. History/Settings stay neutral.
State colors: `SEALED=CLOSED=green`, `OPEN (<threshold)=amber`, `OVERDUE (>threshold)=red pulsing`, `STALE=amber`, `OFFLINE=grey`.

Live pill (header, all screens):
- `● green = LIVE` (last-seen <=10s)
- `● amber = STALE` (>10s)
- `● red/grey = OFFLINE` (ws disconnected). Timer pauses, shows `--:--`.

## 4. Screen 1 — Status / Home v3 (CURRENT)
Minimal. Only door + 1 word + 1 timer + 1 bar + nav. Nothing else on main view.

```
┌──────────────────┐
│ ❄︎       ●       │  logo left, live dot right. No text.
│                  │
│   ┌──────────┐   │
│   │          │   │  BIG DOOR, ~70% height, centered
│   │          │‖  │  closed: shut / open: ajar with light gap
│   │          │‖  │
│   └──────────┘   │
│      OPEN        │  one word: SEALED green / OPEN amber-red
│      01:32       │  one mono timer. hidden when SEALED.
│   ━━━━━━━░░░░    │  one thin threshold bar. no numbers.
│ [Status][Hist][Set]│
└──────────────────┘
```

### 4.1 Big Door spec
- Flat steel panel, sharp 8px corners, 2px edge light. No 3D fridge, no snowflakes, no background scene.
- Fill: `#16213A` + subtle vertical brushed gradient. Handle: small vertical bar, right side, `#0B1220` on `#1E293B`.
- CLOSED/SEALED: front view, no gap, 2px `#22C55E` outer glow. Static, stays shut.
- OPEN: same panel + right edge swung ~12deg perspective. 12px gap on right: cold spill `#67E8F9` → transparent. Border 2px `#F59E0B`. If overdue: pulse `#EF4444`.
- Animate open/close 250ms, no bounce.
- Offline: door greys out (desaturate, grey border), timer `--:--`.

### 4.2 Behavior table
| State | Word | Timer | Bar | Door |
|---|---|---|---|---|
| Closed | SEALED green | hidden | empty green | shut |
| Open < threshold (e.g. 30s) | OPEN amber | white mono ticking | filling cyan | ajar + cyan spill |
| Open > threshold | OPEN red | red mono pulsing | full red | ajar + red pulse |
| Offline | SEALED/OPEN grey | `--:--` | frozen | greyed |

### 4.3 Text REMOVED from home (do not re-add)
Do NOT show on home main view: `DOOR STATE` label, `Device: esp32-freezer-01`, `Last seen: X sec ago` paragraph, `Threshold: 30s fw 1.0.0`, `📶 -48dB`, `🕐 uptime`, `◯ 68%`, `01:32 / 00:30` dual numbers, `⚠ DOOR OPEN` banner paragraph, `STALE/OFFLINE` paragraph.
- Details (RSSI, uptime, device id, threshold, cfg version, fw, last-seen) live in tap-door bottom sheet + Settings > Device. Not on home.
- Overdue has NO banner text wall. Red door + red timer IS the alert. Optional inline actions under bar: `[ Acknowledge ] [ Mute 10m ]`.

## 5. Screen 2 — History
Timeline, not flat list. Sticky segmented filter, not chips.

```
│ History                  [⟳][⌕] │
│ (7) events • esp32-freezer-01   │
│ [All|Open|Closed|Alert]         │ segmented control, persists
│ ●────○ DOOR OPEN                │
│ │    7:01:48 PM                 │
│ ●────○ OVERDUE +45s ⚠           │ red rail + duration badge
│ ●────○ CLOSED 1m14s ✓           │ green, "door safe"
│      [ Load more (23 left) ]    │ pagination
```

- Left rail dots: cyan=open, green=closed, red=overdue, amber=stale/offline.
- Card: `Title + relative + absolute`. Ex: `OVERDUE • 2m ago • 7:02:18 PM` + chip `+45s over`. Closed shows `opened for 1m 14s`.
- Pull-to-refresh + skeleton. Empty: `🧊 No events yet — open the freezer door to test` + `[ Simulate ]`. Error: `Couldn't load • Retry`.
- Filter counts in header.

## 6. Screen 3 — Settings
3 grouped cards + sticky save. Status header on top, not footer.

```
│ Settings                            │
│ ● Connected to 10.44.179.86         │
│ ┌ SERVER ─────────────────────────┐ │
│ │ URL [http://10.44.179.86:8000]  │ │
│ │ [Test]  ✓ 42ms • v4 api         │ │ inline result, green ✓ / red ✗
│ └─────────────────────────────────┘ │
│ ┌ ALERTS ─────────────────────────┐ │
│ │ Threshold [— 30s +] + slider    │ │ 5–1800 validated, hint: Warn at 0:30
│ │ Repeat    [— 0 off +]           │ │ 0 = once/off
│ │ Buzzer              [toggle]    │ │
│ │ Push [off] needs FCM setup ⓘ    │ │ disabled + explainer
│ └─────────────────────────────────┘ │
│ ┌ DEVICE ─────────────────────────┐ │
│ │ esp32-freezer-01 [copy]         │ │
│ │ cfg v4 • fw 1.0.0 • -48dBm      │ │
│ └─────────────────────────────────┘ │
│ [ Save changes* ] sticky, disabled until dirty, snackbar on save │
```

- Threshold: stepper + slider, 5–1800s. Repeat: stepper, 0 = off.
- Test connection inline. Save sticky bottom, `*` = dirty. Snackbar: `✓ Saved to device` / error red.

## 7. What NOT to do
- No extra cards/paragraphs on home. Max 2 texts (state + timer).
- No `%` ring labels, no dual `01:32 / 00:30` numbers, no `DOOR STATE` headings.
- No rounded bubbly 20px cards on home. Sharp 8px, 2px borders, one glow.
- No emojis in UI except status icons. No lorem explanations.
