from generics.process import ProcessLike
from utilities.Message import Message


class KeyValueProcess(ProcessLike):
    def __init__(self, name, client, model, store_key_value_pair):
        super().__init__(name, client, model)

        self.store_key_value_pair = store_key_value_pair

        store_key_value_pair_API = {
            "type": "function",
            "function": {
                "name": "store_key_value_pair",  # Name must match implementation
                "description": "Save key-value pairs to memory",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Key used for later retrieval of information. It should be one keyword describing the nature of the associated information (and not contain the piece of information itself)."
                        },
                        "value": {
                            "type": "string",
                            "description": "Piece of information to store"
                        }
                    },
                    "required": ["key", "value"]
                }
            }
        }
        self.functions.append(store_key_value_pair_API)

    def messages(self, context):
        return [
            Message(role="system",
                    content=f"The following message contains potentially useful information which you may decide to store in a key value store using 'store_key_value_pair' tool."
                            f"If more than on piece of information is important, store them using as many call to this tool as necessary."
                            f"If no information is important however, do not call the tool and do not answer anything. Message: '{context}'")
        ]