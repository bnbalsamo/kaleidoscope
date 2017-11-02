#!/bin/sh

KALEIDOSCOPE_API_URL=http://localhost:5000 KALEIDOSCOPE_IMG_ROOT=$(pwd)/imgs FLASK_APP=kaleidoscope python -m flask run -h 0.0.0.0 -p 5000
