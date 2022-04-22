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
  apt-mark hold "$ffmpeganddependents"
  apt-get update -y
  apt-get upgrade -y
  # re-add ffmpeg's repo
  apt-mark unhold "$ffmpeganddependents"
  printf "\ndeb http://deb.debian.org/debian bullseye contrib non-free\ndeb http://deb.debian.org/debian experimental main\ndeb http://deb.debian.org/debian unstable main\n" >>"/etc/apt/sources.list.d/debian-extended.list"
  apt-get update -y
  # i tried to use it with $ffmpeganddependents but it broke i think this is fineeeee
  apt-get install -t experimental -y ffmpeg
  apt autoremove -y
  echo "Done!"
}

# mediaforge ascii art :3
base64 -d <<<"bGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGwqICAiICAgICAgICAgICAgIF1sbGxsbGxsICAgamxsbGxsICAgbGxsbGxsbGxsbGxsbGwgIF1MICBdbGxsbGxsbGxsbGwKbGxsbGxsbGxsKiAgICAgICAgICAgICAgICAsZ2xsbGxsbGxsICAgIFxsbCQgICAgaWwkKiIiKiVsbEYiIiIgIF1sIiJqbEZeIiIqJGxsbGwKbGxsbGxsbGxsTCAgICAgICAgICAgICAgLCRsbGxsbGxsbGxsICB8ICB9QCAgIyAgaUwgIE1NICB9TCAgQEAgIF1sICB8bHdnQEwgIGxsbGwKbGxsbGxsbCogICAgICAgICAgICAgICwkbGxsbGxsbGxsbGxsICB8bCwgICAkbCAgaUwgIGdnZ2dAICAgbGwgIF1sICB8RiAgLCwgIGxsbGwKbGxsbGwqICAgICAgICAgICAgICAgICAqbGxsbGxsbGxsbGxsICB8bGx3dyRsbCAgaWwsICAgICxdJiwgICAgIF1sICB8TCAgICwgIGxsbGwKbGxsbGwsICAgICAgICAgICAgICAgICAgICpsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsQCwgICAgICAgLGcmLCAgICAgICAgIiRsbGxsbGxsICAgICAgIGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGwkeSAgICwkbGxsbEAsICAgICAgICAnJmxsbGxsICAgbGxsbGwmKiIiKiZsbCoqJioqbEYqIioqKmpsTSoiKipsbGxsbGxsbGwKbGxsbGxsbGxsbCRAJGxsbGxsbGxsJHkgICAgICAgIGBZbGxsICAgICAgfEwgIGdnICAnbCAgLHdnTCA6JEwgICQgICwmdyAgbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsdyAgICAgICAgIGxsICAgJCQkJCAgXWxsTCAgbCAgfGxsJCAgLCwsJGwgIDt3d3d3bGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxnLCAgICAgZ2xsICAgbGxsbCYsICAgICwkbCAgfGxsJiAgICAgIFl3ICAgICAsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGksLHtsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsLCAnIicgLCRsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbCQkJCQkbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGw="
printf "\n\n"

if [ "$AUTOMODE" == "ON" ] && [ "$CONFIG" != "" ]; then
  echo "We're in automode. Running MediaForge"
  if [ "$AUTOUPDATE" == "ON" ]; then
    updategit
    updateapt
  fi
  echo "$CONFIG" | base64 -d >config.py
  python -m poetry run python main.py
  exit
fi

PS3='What would you like to do? '
foods=("Run MediaForge" "Edit Config" "Update MediaForge" "Update APT Packages" "Update MediaForge & APT Packages" "Debug Shell" "Quit")
select fav in "${foods[@]}"; do
  case $fav in
  "Run MediaForge")
    python -m poetry run python main.py
    ;;
  "Edit Config")
    nano config.py
    ;;
  "Update MediaForge")
    updategit
    ;;
  "Update APT Packages")
    updateapt
    ;;
  "Update MediaForge & APT Packages")
    updategit
    updateapt
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
