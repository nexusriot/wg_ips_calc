#!/bin/env bash
set -e
echo "running core test"
python3 -m unittest test_wg_ips_core.py

echo "building linux bin"
pyinstaller --windowed --add-data="resources/icon.ico:resources/." --onefile --icon=resources/icon.ico wg_ips_gui.py
