# earthquake-rescue-system

Air-ground coordinated post-earthquake rescue auxiliary decision system (AGCDR): ground vehicle + drone + host software.

For complex post-earthquake rubble scenes: the ground vehicle and the drone collect positioning and live video in sync, while the host software shows both devices' positions, trajectories and sensor data on a map in real time, and controls each device independently in manual, line-tracking and obstacle-avoidance modes. The system addresses coordinate/map mismatch, trajectory loss offline, unstable dual video streams, and hard-to-coordinate air-ground control, giving rescue command real-time situational awareness and decision support.

> This is the open-source code repository of AGCDR, a national-level university innovation project.

## Layout

```
earthquake-rescue-system/
├── firmware/    # ESP32 smart-car firmware (Arduino)
├── software/    # Rescue command host (Python + Flask)
├── docs/        # Hardware / software / setup guides
└── .github/workflows/ci.yml
```

See [README.md](README.md) (Chinese) for the full guide, including quick start, the three modes, and the security notes on keys and passwords.

## License

Apache-2.0, see [LICENSE](LICENSE).
