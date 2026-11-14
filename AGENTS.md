# AGENTS.md

Working notes for agents contributing to this repo.

## Layout

- `firmware/SmartCar_System/` — ESP32 Arduino firmware. Entry: `SmartCar_System.ino`.
  Modules: `SpeedDrive` (motors + speed), `TraceControl` (line tracking),
  `AvoidControl` (ultrasonic + servo scan), `WebHandler` (web console, AP+STA).
- `firmware/camera/` — onboard camera web UI (`camera_web.html`, GC2145):
  served on `:80`, MJPEG stream on `:81/stream`; this is the device
  `software/config.py` calls `ONBOARD_IP`, separate from the car control IP.
- `software/` — Python host. Entry: `web_server.py` (Flask console).
  `car.py` talks to the car over HTTP (`/cmd`, `/mode`); `detection.py`
  does colour segmentation + ArUco localisation; `decision.py` decides
  stop/continue; `deepseek.py` is an optional tactical-advisor call.
  `rescue_controller.py` is the OpenCV-window fallback controller.
  Frontend lives in `software/web/index.html` (loaded by `web_server.py`
  from `web/index.html`, not from Flask `templates/`).
- `software/demo/` — hardware-free full-process concept demo
  (`sim_tactical_brain_cartoon.py`): stage 1 traditional straight-line
  failure vs stage 2 A* green route with human-in-the-loop, for
  presentations. See `software/demo/README.md`.
- `tools/` under `software/` — camera-index probe and HSV calibration helpers.

## Rules

- Never commit real secrets: Wi-Fi passwords, API keys, or site IPs.
  Keys come from environment variables only (`DEEPSEEK_API_KEY`,
  `CAR_IP`, `ONBOARD_IP`). Ship `.example` files, never the real config.
- Keep the middle register in public-facing docs: technical, but do not
  disclose specific hardware models or core algorithm details beyond
  what the code itself already shows.
- Small, conventional commits: `feat:`, `fix:`, `docs:`, `ci:`, `chore:`.
- Before pushing, run `python -m py_compile software/*.py software/tools/*.py software/demo/*.py`
  and `python -m pytest software/tests -q`, and make sure CI (arduino-cli compile
  of the firmware) is green.
- Detection noise is fixed in `detection.py`, not by widening HSV ranges:
  tune `MIN_ZONE_AREA`, `ZONE_MERGE_PX`, `ZONE_PERSIST_FRAMES` and `ROI`
  in `config.py` first; re-calibrate HSV with `software/tools/probe_color.py`
  when the lighting changes.
