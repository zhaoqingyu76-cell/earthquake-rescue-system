# earthquake-rescue-system

Post-earthquake rescue path assessment system based on air-ground coordination and a semantic risk cost map.

An overhead panoramic camera surveys the scene, classifies water, pits and collapsed buildings into a semantic risk cost map, and the system computes a coordinate-navigation suggestion ("turn right X°, then drive straight") that the operator executes manually with WASD. **Human in the loop, zero autonomous driving** — the host only suggests and assesses; it never drives the vehicle.

## What it does

| # | Module | Function |
|---|---|---|
| 1 | Panoramic perception | HSV segmentation of three terrain types + ArUco localisation of the vehicle (position and heading); the vehicle itself is excluded from detection |
| 2 | Coordinate navigation | Lock the vehicle, select a target zone, get a suggested turn angle with an AR arrow overlay; the operator confirms and drives manually |
| 3 | Collapse-sector prediction | Once a purple collapse zone is locked, a red sector (~94° opening) marks the area the wall could topple onto |
| 4 | Three control modes | Manual / line-tracking / obstacle-avoidance; WASD is hold-to-move, release-to-stop |
| 5 | Onboard-camera fallback | Auto-detects the onboard stream (`:81/stream`), runs near-range HSV detection, reconnects on drop |
| 6 | DeepSeek risk assessment | Tactical assessment of the locked hazard zone only; local fallback text when no key, offline, or timed out |

## Colour convention

| Colour | Meaning |
|---|---|
| Cyan-blue | Water |
| Red | Pit |
| Purple | Building / collapse zone |
| Red (translucent sector) | Predicted collapse sweep area |

## Layout

```
earthquake-rescue-system/
├── firmware/    # ESP32 smart-car firmware (Arduino) + ESP32-CAM web UI
├── software/    # Rescue command host (Python + Flask, WASD manual control)
├── docs/        # Hardware / software / setup guides
└── .github/workflows/ci.yml
```

See [README.md](README.md) (Chinese) for the full guide, including quick start, on-site calibration, safety constraints, and security notes on keys and passwords.

## Safety

Never commit real secrets. IPs and keys are placeholders (`YOUR_CAR_IP`, `YOUR_DEEPSEEK_API_KEY`); fill them in local config only — see [docs/setup.md](docs/setup.md).

## License

Apache-2.0, see [LICENSE](LICENSE).
