#!/bin/bash
# Script to replace em-dashes with appropriate punctuation

sed -i.bak '
s/outputs—let/outputs. Let/g
s/agents—Claude/agents (Claude/g
s/algorithms\./algorithms)./g
s/workflow—the/workflow, the/g
s/strengths—architecture/strengths: architecture/g
s/problems—his/problems, his/g
s/manually—only/manually. Only/g
' index.html

echo "Em-dashes replaced successfully"
