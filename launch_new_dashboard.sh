#!/bin/bash
# Launch new consolidated dashboard on port 8502

echo "Starting new consolidated dashboard on port 8502..."
streamlit run src/dashboard/app.py --server.port 8502 --server.address localhost
