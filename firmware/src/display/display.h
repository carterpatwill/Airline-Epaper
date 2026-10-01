// The shared e-paper display object + one-time init. All drawing goes through
// this single GxEPD2 instance. Panel/pin config: see ../HARDWARE.md.
#pragma once
#include <GxEPD2_BW.h>

extern GxEPD2_BW<GxEPD2_750_GDEY075T7, GxEPD2_750_GDEY075T7::HEIGHT> display;

// Bring up HSPI + the panel (call once from setup()).
void displayInit();
