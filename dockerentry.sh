#!/bin/bash
PS3='What would you like to do? '
foods=("Run MediaForge" "Edit Config" "Update MediaForge" "Debug Shell" "Quit")
select fav in "${foods[@]}"; do
  case $fav in
  "Run MediaForge")
    python -m poetry run python main.py
    ;;
  "Edit Config")
    nano config.py
    ;;
  "Update MediaForge")
    # remote isnt set up by default when container is set up
    if [ ! -d ".git" ]; then
      git init .
      git remote add origin https://github.com/HexCodeFFF/mediaforge.git
    fi
    git pull origin master
    ;;
  "Debug Shell")
    /bin/bash
    ;;
  "Quit")
    exit
    ;;
  *) echo "invalid option $REPLY" ;;
  esac
done
