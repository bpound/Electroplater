#!/bin/bash

cd "/home/pi/Desktop/electroplating_source"
source "electroplating_source/bin/activate"
python3 "Electroplating_code.py"
deactivate
echo "\nClosing window in 10 seconds."
sleep 10
