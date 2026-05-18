import base64
from generics.memory import MemoryLike


class GraphicalMemory(MemoryLike):
    def __init__(self, client, incremental=False):
        super().__init__()
        self.client = client
        self.image_model = "gpt-image-1"
        self.text_model = "gpt-4.1-mini"
        self.text_detail_high = False
        self.size = 1024
        self.location = "output/graphicalMemory/image.png"
        self.incremental = incremental

    def _text_prompt(self, query=None):
        if query is None:
            prompt = "Describe this image."
        else:
            prompt = f"This image may contain information about the following query: '{query}'. Answer it using details from the image only."

        return prompt

    def get(self, query=None) -> list:
        with open(self.location, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = self.client.responses.create(
            model=self.text_model,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": self._text_prompt(query)},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/jpeg;base64,{image_b64}",
                        "detail": "high" if self.text_detail_high else "low"
                    },
                ],
            }],
        )

        return [response.output_text]

    def _image_prompt(self, data):
        ...

    def _edit_prompt(self, data):
        ...

    def put(self, data, metadata=None):
        if self.incremental:
            result = self.client.images.edit(
               model=self.image_model,
               image=open(self.location, "rb"),
               #mask=open("mask.png", "rb"),
               prompt=self._edit_prompt(data)
            )
        else:
            result = self.client.images.generate(
                model=self.image_model,
                prompt=self._image_prompt(data),
                size=f"{self.size}x{self.size}",
            )

        image_base64 = result.data[0].b64_json

        with open(self.location, "wb") as f:
            f.write(base64.b64decode(image_base64))