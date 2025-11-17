FlowBench — Flow Measurement Desktop App

This is a starter professional desktop application for measuring and visualising flow characteristics for engine components.

Features

- Live numeric readout of current measurement
- Live plotting (Matplotlib) embedded in the UI
- Simulated data source with clear hardware integration points

Requirements

- Python 3.10+
- PySide6
- matplotlib
- numpy

Quick start

1. Create and activate a venv: python -m venv .venv; .\.venv\Scripts\Activate.ps1
2. Install: pip install -r requirements.txt
3. Run: python -m flowbench.main

Notes

- This scaffold uses a simulator. Replace the simulator module with hardware integration.
