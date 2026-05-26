#!/usr/bin/env python

import argparse

from utilities.EmotionExplorator import EmotionExplorator

parser = argparse.ArgumentParser(description="Generate pictorial representation of an emotion")

# Add arguments
parser.add_argument("--name", "-n", type=str, help="Emotion name (output will be <name.png>)")
parser.add_argument("--description", "-d", type=str, default=None, help="Emotion description (optional). If not provided, the name is used as trigger for the emotion.")

# Parse arguments
args = parser.parse_args()

ee = EmotionExplorator(args.name, args.description)
ee.generate()
print(ee.get()[0])

