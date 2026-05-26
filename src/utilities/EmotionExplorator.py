import base64

from utilities.client import default_client


class EmotionExplorator:
    def __init__(self, name, emotion=None, out_path="results/emotions", client=default_client):
        super().__init__()
        self.image_model = "gpt-image-1"
        self.text_model = "gpt-4.1-mini"
        self.name = name
        self.emotion = emotion if emotion is not None else self.name
        self.size = "1024x1024"
        self.text_detail_high = False
        self.file_path = f"{out_path}/{self.name}.png"
        self.client = client

    def _image_prompt(self, data):
        return (f"Create an abstract image capturing the mood/emotion given by the following description: '{data}'. "
                f"Use lines, colors, and textures, rather than recognizable iconic representations, symbols, words, or human beings.")

    def generate(self):
        result = self.client.images.generate(
            model=self.image_model,
            prompt=self._image_prompt(self.emotion),
            size=self.size,
        )

        image_base64 = result.data[0].b64_json

        with open(self.file_path, "wb") as f:
            f.write(base64.b64decode(image_base64))

    def get(self) -> list:
        """
        Associate a mood/emotion from an image
        :return:
        """
        with open(self.file_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.responses.create(
            model=self.text_model,
            input=[
               {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": f"Which moods/emotions/feelings are conveyed in this image? Answer with three words (first word being the best matching). Ex: 'sad, anger, frightened'."
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