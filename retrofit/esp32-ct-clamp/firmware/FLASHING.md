# Flashing the esp32-ct-clamp Firmware

**Status: DRAFT firmware - never compiled or run by its author.** Expect to
fix build errors on the first `pio run`; please PR them. See the
[README](../README.md) before deploying anything.

```bash
cd retrofit/esp32-ct-clamp/firmware
pip install platformio
pio run                 # compile
pio run -t upload       # board connected via USB
pio device monitor      # watch the serial log (115200)
```

- Board: ESP32-WROOM-32 dev board (`esp32dev`). The -C3 minimal boards have
  a different ADC and are not supported by this build.
- Prebuilt release binaries and a GUI-flasher walkthrough will accompany
  releases once the firmware has hardware validation.
- To re-enter provisioning after flashing: hold the BOOT button while
  powering on.
