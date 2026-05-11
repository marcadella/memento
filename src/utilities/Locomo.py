import json
from pathlib import Path

import requests
import yaml


class Locomo:
    def __init__(self, output_path="output"):
        self.output_path = output_path

    def conversation(self, conversation_id):
        locomo_file = "dataset/locomo10.json"
        if not Path(locomo_file).exists():
            r = requests.get("https://github.com/snap-research/locomo/raw/refs/heads/main/data/locomo10.json")
            r.raise_for_status()

            with open(locomo_file, "wb") as f:
                f.write(r.content)

        with open(locomo_file, "r") as f:
            conversation = json.load(f)[conversation_id]["conversation"]

        name1 = conversation["speaker_a"]
        name2 = conversation["speaker_b"]

        tape = []
        for k, item in conversation.items():
            if type(item) is list:
                for session in item:
                    tape.append({session["speaker"]: session["text"]})
                    if "blip_caption" in session.keys():
                        tape.append({session["speaker"]: f"Here is {session["blip_caption"]}."})

        conv_name = f"locomo_{conversation_id}"
        conv_path = f"{self.output_path}/{conv_name}.yaml"
        with open(conv_path, "w", encoding="utf-8") as f:
            yaml.dump(tape, f, width=float("inf"))

        return name1, name2