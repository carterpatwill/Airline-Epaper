// Hardware pin map + build-time feature flags for the reTerminal E1001.
// Panel/pin details and board notes: see ../HARDWARE.md.
#pragma once

// ---- ePaper pins (reTerminal E1001, HSPI) ----------------------------------
#define EPD_SCK_PIN   7
#define EPD_MOSI_PIN  9
#define EPD_CS_PIN    10
#define EPD_DC_PIN    11
#define EPD_RES_PIN   12
#define EPD_BUSY_PIN  13

// Green center button = refresh/wake (active-low, INPUT_PULLUP -> LOW=pressed).
#define BTN_REFRESH   3
// The two TOP WHITE nav buttons switch screens (active-low, INPUT_PULLUP).
#define BTN_RIGHT     4   // right white -> MAP screen
#define BTN_LEFT      5   // left  white -> DETAILS screen
// Onboard green LED (active-low: LOW = on). Used as instant press feedback.
#define LED_GREEN     6

// Battery sense (reTerminal E1001): a 1:2 divider on GPIO1, gated by a P-FET on
// GPIO21. Drive enable HIGH, settle, read analogReadMilliVolts(), drive LOW.
// Actual pack voltage = measured * 2. Source: Seeed Arduino peripherals wiki.
#define BAT_ADC_PIN     1
#define BAT_ENABLE_PIN  21

// DEBUG: stay awake and refresh on a short interval (no deep sleep, button not
// needed) so we get immediate, repeated feedback on-screen. Set 0 for the real
// battery-saving deep-sleep behaviour.
#define DEBUG_STAY_AWAKE 1

// GALLERY: ignore live flights and instead show each plane-art image in turn.
// Press the green center button to flip to the next one (wraps around). Set 0
// for normal operation.
#define GALLERY_MODE 0
