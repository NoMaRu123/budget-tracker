#!/bin/bash

# Install your Python environment
apt-get update -y
apt-get install -y python3.14-venv
python3.14 -m venv venv
source venv/bin/activate

# Clone the latest app directly onto the server
git clone https://github.com/NoMaRu123/budget-tracker.git
cd budget-tracker/backend
pip install -r requirements.txt

# Run Uvicorn on port 80 bound to all interfaces, in the background with a log file
uvicorn main:app --host 0.0.0.0 --port ${app_port} > uvicorn.log 2>&1 &
