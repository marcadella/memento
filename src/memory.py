from process import ProcessLike


class MemoryLike(ProcessLike):
    """
    A memory is a file (virtual or not) which an agent process can interact with using functions.
    """
    def __init__(self, name, client, model):
        super().__init__(name, client, model)

class KeyValueMemory(MemoryLike):
    def __init__(self, name, client, model):
        super().__init__(name, client, model)
        self.kv_store = {}
        store_key_value_pair_API = {
            "type": "function",
            "function": {
                "name": "store_key_value_pair", # Name must match implementation
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

    def store_key_value_pair(self, key, value):
        """
        Stores a key-value pair
        :param key:
        :param value:
        :return:
        """
        self.kv_store[key] = value
        print(f"***** Memorizing({key}: {value})\n")

    def read_all(self):
        """
        Read all key-value pairs stored in memory.
        :return: Markdown format
        """
        memorized_items = [f"- {k}: {v}" for k, v in self.kv_store.items()]
        return "\n".join(memorized_items)

    def messages(self, context):
        return [{"role": "system",
                 "content": f"The following message contains potentially useful information which you may decide to store in a key value store using 'store_key_value_pair' tool." 
                            f"If more than on piece of information is important, store them using as many call to this tool as necessary."
                            f"If no information is important however, do not call the tool and do not answer anything. Message: '{context}'"}]