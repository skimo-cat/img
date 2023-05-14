#!/bin/bash

cd /home/pi/skimo-img
.  /home/pi/skimo-img/venv/bin/activate && python3 fetch.py
#for X in img/*.jpeg; do convert "$X" -scale 25% -size 25% -strip -quality 90 "${X}_converted" && mv "${X}_converted" "$X" ; done
git config --global user.name 'skimo'
git config --global user.email 'skimoskimo@skimo.com'
git checkout --orphan latest_branch
git add -A
git commit -m "Automated"
git branch -D main
git branch -m main
git push -f origin main
rm -Rf .git/logs/
rm -Rf .git/refs/original
git prune
git gc --aggressive --prune=now
