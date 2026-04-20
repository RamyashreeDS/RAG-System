#!/bin/bash
pandoc MediGuide_Technical_Report.md -o MediGuide_Technical_Report.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=1in \
  -V fontsize=11pt \
  --toc --toc-depth=3 \
  -V colorlinks=true \
  -V linkcolor=blue
