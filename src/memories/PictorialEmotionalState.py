import base64
import os
import shutil
from pathlib import Path

from generics.memory import MemoryLike
from utilities.Context import ctx
from utilities.EmotionExplorator import EmotionExplorator
from utilities.client import default_client


class PictorialEmotionalState(MemoryLike):
    def __init__(self, client=default_client, initial_emotional_state="results/emotions/sad.png", skip_generation=False):
        super().__init__()
        self.client = client
        self.image_model = "gpt-image-1"
        self.text_model = "gpt-4.1" #Do not use mini!
        self.text_detail_high = False
        self.size = "1024x1024"
        self.initial_emotional_state = initial_emotional_state
        self.last_location = self.initial_emotional_state if os.path.exists(self.initial_emotional_state) else None
        self.skip_generation = skip_generation

    def _location(self):
        return f"{ctx.current_path()}_image.png"

    def _text_prompt(self, query=None):
        if query is None:
            prompt = "Describe this image."
        else:
            prompt = f"This image may contain information about the following query: '{query}'. Answer it using details from the image."

        return prompt

    def get(self, query=None) -> list:
        """
        Modulate the text provided in the query field based on the mood of the image
        :param query:
        :return:
        """
        with open(self.last_location, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.responses.create(
            model=self.text_model,
            input=[
                {"role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"You are assisting a writer to change the tone of his writing based on visual cues. "
                                f"Your task is to rewrite what the user asks you to rewrite by solely changing the tone. "
                                f"In other words, impersonate someone having the mental state based on the provided image and adapt the tone accordingly. "
                                f"Do NOT mention the image: it is simply provided to guide your tone."
                    }
                    ]
                 },
               {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Text to rewrite: '{self._text_prompt(query)}'."
                    },
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_b64}",
                        "detail": "high" if self.text_detail_high else "low"
                    },
                ],
            }],
        )

        return [response.output_text]

    def _image_prompt(self, data):
        return (f"Create an abstract image capturing the mood/emotion given by the following description: '{data}'. "
                f"Use lines, colors, and textures, rather than recognizable iconic representations, symbols, words, or human beings.")

    def _edit_prompt(self, data):
        #transform some areas slightly
        return (f"Without changing drastically the picture, add a few touches (less than 10% of the surface should change) to incorporate a change of mood/emotion/feeling induced by the provided text. "
                f"The image should remain abstract. Do not draw smileys or human faces as this would be unprofessional."
                f"Use lines, colors, and textures, rather than recognizable iconic representations, symbols, words, or human beings."
                f"Text: '{data}'")

    def put(self, data, metadata=None):
        new_location = self._location()
        if self.skip_generation:
            shutil.copy(self.last_location, new_location)
        else:
            if self.last_location is not None and os.path.exists(self.last_location):
                print(f">>> Editing emotion {self.last_location}")
                result = self.client.images.edit(
                    model=self.image_model,
                    image=open(self.last_location, "rb"),
                    # mask=open("mask.png", "rb"),
                    prompt=self._edit_prompt(data)
                )
            else:
                result = self.client.images.generate(
                    model=self.image_model,
                    prompt=self._image_prompt(self.initial_emotional_state),
                    size=self.size,
                )

            image_base64 = result.data[0].b64_json

            with open(new_location, "wb") as f:
                f.write(base64.b64decode(image_base64))

        #path = Path(new_location)
        #new_emotions = EmotionExplorator(path.name.removesuffix(".png"), out_path=path.parent, client=self.client).get()
        #print(f">>> New emotion {new_location}: {new_emotions}")

        self.last_location = new_location
