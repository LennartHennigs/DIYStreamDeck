#!/bin/bash
# Kill any process already on port 8001
lsof -ti tcp:8001 | xargs kill -9 2>/dev/null
cd "$(dirname "$0")"/src/mac/config-tool
python3 -m http.server 8001 &
sleep 1
open http://localhost:8001/