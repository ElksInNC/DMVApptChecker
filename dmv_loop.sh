#!/bin/bash

while true; do
  echo "[$(date)] Running DMV check..."
  python3 ./checker.py

  delay=$((240 + RANDOM % 61))  # 180–241 seconds
  echo -n "⏳ Sleeping for $delay seconds: "

  while [ $delay -gt 0 ]; do
    printf "\r⏳ Sleeping for %3d seconds..." "$delay"
    sleep 1
    ((delay--))
  done

  echo -e "\r✅ Countdown complete. Starting next check...      "
done