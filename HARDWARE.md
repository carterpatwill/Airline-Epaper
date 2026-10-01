# Hardware Reference — Seeed Studio reTerminal E1001

Source: Seeed Studio Wiki, "Getting Started with reTerminal E1001"
(https://wiki.seeedstudio.com/getting_started_with_reterminal_e1001/)

## Specification
| Item | Description |
|------|-------------|
| Product | reTerminal E1001 |
| Processor | **ESP32-S3 with 8MB PSRAM** |
| Storage | **32MB Flash**, microSD (≤32GB, **FAT32**) |
| Display | 7.5" **Monochrome** ePaper (4-level grayscale in practice) |
| Resolution | **800 × 480** |
| Wireless | **2.4GHz only** Wi-Fi b/g/n, Bluetooth 5.0 |
| Sensors | Temperature, humidity |
| Audio | Microphone (reserved), buzzer |
| Battery | 2000mAh (~3-month life at default refresh) |
| Power in | USB-C 5V/1A |
| Temp range | 0–40°C |
| Dimensions | 176 × 120 × 53mm (with stand) / 17mm (without) |

## Hardware Overview (front + back)
- **7.5" ePaper display** — 800×480 monochrome.
- **Top buttons**: **Refresh/Wake** (green), plus **Left** / **Right** nav buttons.
  Microphone pin-holes sit alongside them.
- **Refresh button**: single press = refresh + check for content + wake; the
  primary way to **wake the device from sleep** (needed before flashing).
- **Nav buttons**: left = prev page, right = next page. Hold **both for 2s** =
  Wi-Fi reset / reconfig mode.
- **Back**: microSD slot, **power switch (ON/OFF)**, USB-C port (charge + flash),
  **8-pin expansion header (J2)**, status LED (green), charge LED (red).
- **LEDs**: green on ~30s at boot; red solid = charging, off = charged/idle;
  low-battery icon shows when <20%.

## Buttons (confirmed — Seeed ESPHome cookbook)
Active-low, `INPUT_PULLUP` (LOW = pressed).
| Button | GPIO |
|--------|------|
| Green center (refresh/wake) | **GPIO3** |
| Right white (nav) | GPIO4 |
| Left white (nav) | GPIO5 |

Deep-sleep wake: Seeed uses **GPIO4** (right button) as the recommended ext
wake pin (using the green button as wake can complicate USB uploads while
asleep). GPIO3/GPIO4/GPIO5 are all RTC-capable so any can be an ext0/ext1 wake
source. Our firmware currently polls GPIO3 (green) for on-demand refresh in
stay-awake mode.

## Expansion Header J2 (8-pin) — the ONLY documented external GPIO
| Pin | Label | ESP32-S3 | Function |
|-----|-------|----------|----------|
| 1 | HEADER_3V3 | — | 3.3V out |
| 2 | GND | — | Ground |
| 3 | ESP_IO46 | GPIO46 | GPIO / ADC |
| 4 | ESP_IO2 | GPIO2 | GPIO / ADC1_CH4 |
| 5 | ESP_IO17 | GPIO17 | GPIO / UART TX1 |
| 6 | ESP_IO18 | GPIO18 | GPIO / UART RX1 |
| 7 | ESP_IO20 | GPIO20 | GPIO / I2C0 SCL |
| 8 | ESP_IO19 | GPIO19 | GPIO / I2C0 SDA |

## ePaper display config (CONFIRMED — Seeed Arduino cookbook)
Source: https://wiki.seeedstudio.com/reterminal_e10xx_with_arduino/ and the
**Seeed_GxEPD2** fork (https://github.com/Seeed-Projects/Seeed_GxEPD2).

- **Libraries**: install **Seeed_GxEPD2** (Seeed's fork, NOT stock GxEPD2) +
  **Adafruit GFX Library**.
- **Panel**: 7.5" B&W **GDEY075T7**, 800×480, **UC8179** controller.
- **GxEPD2 class**: `GxEPD2_750_GDEY075T7`
- **SPI pins** (HSPI):

  | Signal | GPIO |
  |--------|------|
  | SCK    | 7  |
  | MOSI   | 9  |
  | CS     | 10 |
  | DC     | 11 |
  | RES/RST| 12 |
  | BUSY   | 13 |

- **No external power-enable pin** needed on E1001.
- **SPI**: HSPI, **2 MHz**, MSBFIRST, SPI_MODE0.
- **Arduino board setting**: **XIAO_ESP32S3**, **OPI PSRAM enabled**.

```cpp
#define EPD_SCK_PIN 7
#define EPD_MOSI_PIN 9
#define EPD_CS_PIN 10
#define EPD_DC_PIN 11
#define EPD_RES_PIN 12
#define EPD_BUSY_PIN 13

GxEPD2_BW<GxEPD2_750_GDEY075T7, GxEPD2_750_GDEY075T7::HEIGHT>
  display(GxEPD2_750_GDEY075T7(EPD_CS_PIN, EPD_DC_PIN, EPD_RES_PIN, EPD_BUSY_PIN));

SPIClass hspi(HSPI);
hspi.begin(EPD_SCK_PIN, -1, EPD_MOSI_PIN, -1);
display.epd2.selectSPI(hspi, SPISettings(2000000, MSBFIRST, SPI_MODE0));
```

- **4-level grayscale**: use the Seeed_GxEPD2 example
  `examples/GxEPD2_reTerminal_E1001_Gray4/` (UC8179 custom LUT + bit-plane
  encoding). Start with `GxEPD2_BW` (1-bit) to bring the panel up, then move to
  Gray4 for the silhouette shading.

## Out-of-box firmware vs. our custom firmware
- Ships running **SenseCraft Seeedash** (no-code cloud dashboards) + a browser
  **Firmware Hub** flasher. That path does NOT run our logic on-device.
- Our project flashes **custom Arduino-ESP32 firmware**, which REPLACES the
  SenseCraft firmware. That's expected and desired (goal = all logic on-device).
  SenseCraft can always be re-flashed later from the Firmware Hub if wanted.

## Mac flashing notes (this user is on macOS)
- Requires the **CH34x/CH340 USB driver** (WCH). On macOS also enable the driver
  extension in System Settings → General → Login Items & Extensions.
- Serial port shows as `/dev/tty.wchusbserial*` — verify with `ls /dev/tty.wch*`.
- Use a **data** USB-C cable, power switch **ON**, and **press the green Wake
  button** first — you cannot flash while the device is asleep/shut down.

## Resources to pull before/while building
- reTerminal E1001 **Schematic (PDF)** — display SPI pins + power gating.
- Seeed **OSHW-reTerminal-Series-E-D** GitHub — Arduino display examples.
- ESP32-S3 datasheet.
