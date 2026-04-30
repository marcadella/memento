class BoundedContext:
    """
    Bounded context utility
    A context is a list of messages of the form `{'role': ..., 'content': ...}`
    In a bounded context, the context may only contain up to `max_content_size` characters when concatenating all the messages' contents.
    When the maximum size is reached, the first messages are being deleted to make enough space for the new messages to come in.
    The first message may be truncated rather than deleted.
    """

    def __init__(self, max_content_size=1000):
        """
        :param max_content_size: Maximum size of the `content` fields in the message list (measured in characters).
        """
        self.max_content_size = max_content_size
        self._context = [] # List of messages (dict containing a `content` field)

    def _current_size(self):
        """
        Return the current size of the content.
        :return: Size (number of characters)
        """
        size = 0
        for message in self._context:
            size += len(message["content"])
        return size

    def _trim_head(self):
        """
        Recursively trim the head of the message list if _current_size > max_content_size.
        """
        delta = self.max_content_size - self._current_size()
        if delta < 0:
            head = self._context[0]
            if delta + len(head["content"]) <= 0:
                self._context = self._context[1:]
                self._trim_head()
            else:
                head["content"] = head["content"][-delta:]

    def append(self, message):
        """
        Append a message to the message list. First messages are discarded or truncated as needed.
        Message must be a dict containing a `role` and `content` fields.
        :param message: Message to append.
        """
        assert "role" in message.keys()
        assert "content" in message.keys()

        self._context.append(message)
        self._trim_head()


    def get(self):
        """
        Get current context
        :return: Current context
        """
        return self._context