#!/bin/bash
PS3='What would you like to do? '
foods=("Run MediaForge" "Edit Config" "Update MediaForge" "Quit")
select fav in "${foods[@]}"; do
  case $fav in
  "Run MediaForge")
    python -m poetry run main.py
    ;;
  "Edit Config")
    nano config.py
    ;;
  "Update MediaForge")
    git pull
    ;;
  "Quit")
    exit
    ;;
  *) echo "invalid option $REPLY" ;;
  esac
done
