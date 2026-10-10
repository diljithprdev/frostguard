# FROSTGUARD — ESP32 Firmware

ESP32 DevKit V1 + A3144 hall sensor. Monitors a freezer door, pushes live state to
the FROSTGUARD backend over TCP (fast path) with HTTP fallback. **Zero external
libraries** — only what ships with the ESP32 Arduino core.

## 1. Wiring

| A3144 module | ESP32 DevKit V1 | Notes |
|---|---|---|
| `+` (VCC) | **3V3** | Power the module at 3.3 V so its output never exceeds 3.3 V. **Never feed 5 V into an ESP32 GPIO.** |
| `-` (GND) | **GND** | Common ground is mandatory — sensor and ESP32 must share GND. |
| `S` (signal) | **GPIO 13** | Change `SENSOR_PIN` in the USER SETTINGS block at the top of `frostguard.ino` if needed. |

Optional buzzer (not required now):

| Buzzer module | ESP32 |
|---|---|
| `+` | **GPIO 14** (then set `BUZZER_ENABLED true`, `BUZZER_PIN 14`) |
| `-` | **GND** |

Magnet: attach to the door edge, sensor on the frame, gap **< 5 mm**.
Avoid strapping pins (0, 2, 12, 15) — GPIO 13/14 are safe.

## 2. Configure (one time)

Open `frostguard.ino` and edit the **USER SETTINGS** section at the top of the same file:

- `WIFI_SSID` / `WIFI_PASSWORD` — 2.4 GHz Wi-Fi (ESP32 has no 5 GHz).
- `SERVER_IP` — your **PC's LAN IP**, not `localhost`.
  Find it: `Win+R` → `cmd` → `ipconfig` → "IPv4 Address" (e.g. `192.168.1.15`).
  The ESP32 cannot reach your PC via `127.0.0.1` — that's the ESP32's own loopback.
- Polarity: boot log prints the raw pin level when the magnet is near, confirm
  `SENSOR_ACTIVE_LOW` matches (most A3144 modules: LOW = field present).

All settings live in that one block — nothing else to edit.

## 3. Flash (Arduino IDE)

1. Open `frostguard/frostguard.ino` in Arduino IDE.
   (If it warns about the folder name, accept — the folder is already named `frostguard`.)
2. **Tools → Board → esp32 → ESP32 Dev Module** (your core 3.3.12 is already installed).
3. **Tools → Port** → select your CP2102/CH340 COM port.
4. Click **Verify (✓)** first. Fix any errors (paste them here if unsure).
5. Click **Upload (→)**. Hold BOOT button on the ESP32 if upload stalls.
6. **Tools → Serial Monitor → 115200 baud**.

## 4. What good logs look like

```
 FROSTGUARD firmware 1.0.0
Sensor pin GPIO13 raw=HIGH (expect LOW when magnet near)
Initial state: OPEN
Wi-Fi joining 'MyWifi' ...
[WIFI] CONNECTED (rssi -55)
[TCP] CONNECTED 192.168.1.15:8081
[DOOR] CLOSED after 0s (overdue was: no)
[CONFIG] applied threshold=30 version=1
```

With the server + dashboard running, the website should flip to OPEN/CLOSED
within ~1 second of moving the magnet.

## 5. Behavior rules

- **Debounce:** 50 ms stable before a state change counts (no bounce spam).
- **Timer:** starts on OPEN, resets on CLOSED; monotonic `millis()`.
- **Overdoor:** when elapsed ≥ threshold → `OVERDUE` event + alarm. Threshold is
  pulled from the backend every 10 s — changing it in the UI needs no reflash.
  If the door is **already open** when you lower the threshold, overdue triggers
  immediately; raising it clears future overdue only on next evaluation — an
  active alarm keeps beeping until the door closes (re-arm rule: close re-arms).
- **Wi-Fi loss:** sensor, timer, events queue, buzzer all keep working locally.
  Events retry over HTTP after TCP is down 15 s; everything auto-reconnects
  every 5 s. Undelivered events are dropped after 60 s (state stays truthful
  via heartbeat).
- **Buzzer:** beeps 250 ms on / 750 ms off while overdue — never continuous;
  silences when the door closes. Disabled by default (no buzzer hardware yet).
- **Reboot:** timers restart from 0; `uptime_seconds` resets; server marks truth.
  After power loss, the door's last state is re-read from the sensor at boot.

## 6. Limits (be honest in your report)

- Prototype for a college project — **not** a certified safety controller.
- Monitors door opening only; does **not** detect refrigerant leakage.
- If the sensor wire breaks, an active-low module reads HIGH → shows OPEN →
  alarms eventually (fail-safe direction), but this is not fault-diagnostic.
