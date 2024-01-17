#!/usr/bin/env python

import re

# One would think that there are simple tools that can extract a subset of font awesome icons and stage them for use.
# Well; there are but there are all paid options.
# This here is a really cheap hack to do the same; it is guaranteed to break in the near future.
# But it is a decent option and will reduce the client assets by about 1MB.
# So here goes
# To generate a list of icons, run this in the static folder
# ff '<i ' | grep 'fa-' | sed -e "s/fa-lg//g" | sed -e "s/.*fa-\([a-zA-Z-]*\).*/\1/g" | sort | uniq

all_the_icons_we_use_in_project = [
    "arrows-rotate",
    "broom",
    "check-double",
    "clock-rotate-left",
    "clone",
    "code-branch",
    "code-compare",
    "download",
    "edit",
    "grip-lines-vertical",
    "list",
    "magnifying-glass",
    "magnifying-glass-plus",
    "pen-to-square",
    "plus",
    "question",
    "sort-down",
    "sort-up",
    "tag",
    "tags",
    "tree",
    "trash",
    "upload",
    "user-tie",
    "xmark"
]

with open("../node_modules/@fortawesome/fontawesome-free/js/solid.js", "r") as f:
    lines = f.readlines()

outlines = []

startre = re.compile(r"^\s*var\s+icons\s+=\s+{\s*$")
endre = re.compile(r"^\s*};\s*$")
printline = True
for line in lines:
    line = line.splitlines()[0]
    if startre.match(line):
        outlines.append(line)
        printline = False
    if endre.match(line):
        printline = True
    if printline:
        outlines.append(line)
    for icon in all_the_icons_we_use_in_project:
        if re.match(r"^\s*\""+icon+r"\":\s*", line):
            outlines.append(line)
            break


with open("../node_modules/@fortawesome/fontawesome-free/js/licco.js", "w") as f:
    f.write("\n".join(outlines))
