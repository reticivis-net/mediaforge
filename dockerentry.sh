#!/bin/bash

updategit() {
  # remote isnt set up by default when container is set up
  echo "Updating MediaForge Code..."
  if [ ! -d ".git" ]; then
    git init . --initial-branch=master
    git remote add origin https://github.com/HexCodeFFF/mediaforge.git
  fi
  git fetch --all
  git reset --hard origin/master
}
updateapt() {
  echo "Updating APT Packages..."
  # ffmpeg's repo conflicts with like everything else, do apt update without it
  rm "/etc/apt/sources.list.d/debian-extended.list"
  # freeze ffmpeg and all dependencies just in case
  ffmpeganddependents=$(apt-cache depends --recurse --no-recommends --no-suggests --no-conflicts --no-breaks --no-replaces --no-enhances ffmpeg | grep "^\w" | tr '\n' ' ')
  apt-mark hold $ffmpeganddependents
  apt-get update -y
  apt-get upgrade -y
  # re-add ffmpeg's repo
  apt-mark unhold $ffmpeganddependents
  printf "\ndeb https://deb.debian.org/debian bullseye contrib non-free\ndeb https://deb.debian.org/debian experimental main\ndeb https://deb.debian.org/debian unstable main\n" >>"/etc/apt/sources.list.d/debian-extended.list"
  apt-get update -y
  # i tried to use it with $ffmpeganddependents but it broke i think this is fineeeee
  apt-get install -t experimental -y ffmpeg
  apt autoremove -y
  echo "Done!"
}
updatepip() {
  # remote isnt set up by default when container is set up
  echo "Updating PIP Packages..."
  python -m poetry install
}

run() {
  # remote isnt set up by default when container is set up
  echo "Running..."
  python -m poetry run python main.py
}

# mediaforge ascii art :3
cat "media/braillebanner.txt"
printf "\n\n"

if [ "$AUTOMODE" == "ON" ] && [ "$CONFIG" != "" ]; then
  echo "We're in automode. Running MediaForge"
  if [ "$AUTOUPDATE" == "ON" ]; then
    updategit
    updateapt
    updatepip
  fi
  echo "$CONFIG" | base64 -d >config.py
  run
  exit
fi

# weird variable name thing for prompt
PS3='What would you like to do? '
choices=("Run MediaForge" "Edit Config" "Update All And Run" "Update MediaForge Code" "Update APT Packages" "Update PIP Packages" "Debug Shell" "Quit")
select fav in "${choices[@]}"; do
  case $fav in
  "Run MediaForge")
    run
    ;;
  "Edit Config")
    nano config.py
    ;;
  "Update All And Run")
    updategit
    updateapt
    updatepip
    run
    ;;
  "Update MediaForge Code")
    updategit
    ;;
  "Update APT Packages")
    updateapt
    ;;
  "Update PIP Packages")
    updatepip
    ;;
  "Debug Shell")
    /bin/bash
    ;;
  "Quit")
    echo "Goodbye!"
    exit
    ;;
  *) echo "invalid option $REPLY" ;;
  esac
done
