#!/usr/bin/env bash
# Automated Slide Builder for Production GenAI API Integrations Course
# Compiles Marp markdown decks in slides/ to interactive HTML presentation decks in dist/slides/

set -e

echo "=========================================================="
echo " Building Presentation Slides (Marp CLI)"
echo "=========================================================="

INPUT_DIR="slides"
OUTPUT_DIR="dist/slides"

mkdir -p "$OUTPUT_DIR"

echo ">>> Compiling slides from '$INPUT_DIR' to '$OUTPUT_DIR'..."

npx --yes @marp-team/marp-cli --no-stdin --input-dir "$INPUT_DIR" -o "$OUTPUT_DIR"

echo ""
echo ">>> Successfully built all presentation decks in $OUTPUT_DIR:"
ls -lh "$OUTPUT_DIR"/*.html
echo ""
echo "Open any HTML file in your browser to present!"

