#!/bin/bash

# mediaforge ascii art :3
base64 -d <<<"bGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGwqICAiICAgICAgICAgICAgIF1sbGxsbGxsICAgamxsbGxsICAgbGxsbGxsbGxsbGxsbGwgIF1MICBdbGxsbGxsbGxsbGwKbGxsbGxsbGxsKiAgICAgICAgICAgICAgICAsZ2xsbGxsbGxsICAgIFxsbCQgICAgaWwkKiIiKiVsbEYiIiIgIF1sIiJqbEZeIiIqJGxsbGwKbGxsbGxsbGxsTCAgICAgICAgICAgICAgLCRsbGxsbGxsbGxsICB8ICB9QCAgIyAgaUwgIE1NICB9TCAgQEAgIF1sICB8bHdnQEwgIGxsbGwKbGxsbGxsbCogICAgICAgICAgICAgICwkbGxsbGxsbGxsbGxsICB8bCwgICAkbCAgaUwgIGdnZ2dAICAgbGwgIF1sICB8RiAgLCwgIGxsbGwKbGxsbGwqICAgICAgICAgICAgICAgICAqbGxsbGxsbGxsbGxsICB8bGx3dyRsbCAgaWwsICAgICxdJiwgICAgIF1sICB8TCAgICwgIGxsbGwKbGxsbGwsICAgICAgICAgICAgICAgICAgICpsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsQCwgICAgICAgLGcmLCAgICAgICAgIiRsbGxsbGxsICAgICAgIGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGwkeSAgICwkbGxsbEAsICAgICAgICAnJmxsbGxsICAgbGxsbGwmKiIiKiZsbCoqJioqbEYqIioqKmpsTSoiKipsbGxsbGxsbGwKbGxsbGxsbGxsbCRAJGxsbGxsbGxsJHkgICAgICAgIGBZbGxsICAgICAgfEwgIGdnICAnbCAgLHdnTCA6JEwgICQgICwmdyAgbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsdyAgICAgICAgIGxsICAgJCQkJCAgXWxsTCAgbCAgfGxsJCAgLCwsJGwgIDt3d3d3bGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxnLCAgICAgZ2xsICAgbGxsbCYsICAgICwkbCAgfGxsJiAgICAgIFl3ICAgICAsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGksLHtsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsLCAnIicgLCRsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbCQkJCQkbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGwKbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGxsbGw="
printf "\n\n"
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
      git init . --initial-branch=master
      git remote add origin https://github.com/HexCodeFFF/mediaforge.git
    fi
    git fetch --all
    git reset --hard origin/master
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
