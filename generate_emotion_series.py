#!/usr/bin/env python

import argparse

from memories.PictorialEmotionalState import PictorialEmotionalState
from utilities.Context import ctx

parser = argparse.ArgumentParser(description="Generate a series of pictorial emotions")

# Add arguments
parser.add_argument("--initial", "-i", type=str, help="Initial emotion")
parser.add_argument("--gradient", "-g", type=str, help="Emotional gradient")
parser.add_argument("--steps", "-s", type=int, help="Number of steps")
parser.add_argument("--prolongate", "-p", type=int, default=0, help="Prolongate a series starting from step p")

# Parse arguments
args = parser.parse_args()

ctx.reset("output/emotion_series")

if args.prolongate > 0:
    initial_emotional_state = f"{ctx.current_path()}/{args.prolongate}_image.png"
else:
    initial_emotional_state = args.initial

ges = PictorialEmotionalState(initial_emotional_state=initial_emotional_state)
for step in range(args.prolongate, args.prolongate + args.steps):
    ctx.append(f"{step}")
    ges.put(args.gradient)
    ctx.pop()


