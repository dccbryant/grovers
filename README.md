# Grover's Search Demo

PyQt6 visualization of Grover's algorithm vs. a classical linear scan, with a 6–14 qubit Qiskit simulator.

## Requirements

- Python 3.10+
- PyQt6
- qiskit

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install PyQt6 qiskit
```

## Run

```bash
python grovers.py
```

## Usage

- **Dial**: select 6–14 qubits (6 = 52-card mode, 7+ = heatmap)
- **STEP**: advance one Grover iteration + one classical check
- **AUTO**: run both engines until each finds the target
- **STOP AT**: target probability Grover must hit before stopping
- **REVEAL**: show card faces / target identity
- **RESTART**: new shuffle, same qubit count
