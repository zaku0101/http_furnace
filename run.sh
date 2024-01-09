#!/bin/sh

if [ -n ${HEATER_NAME} ]
then
  source ~/.venv/bin/activate
  exec flask --app server.py run --host=0.0.0.0
else
  echo "provide HEATER_NAME enviroment variable to run the program"
fi
