from common.message import Message, json_encode, json_decode


class ClientMessage(Message):
    """
    constructor for ClientMessage
    """
    def __init__(self, selector, socket, ipaddr, request):
        super().__init__(selector, socket, ipaddr)
        self._request = request
        self._request_queued = False
        self._response = None

    def _process_read(self):
        """
        process read-event
        :return:
        """
        self._process_headers()

        if self._jsonheader:
            if self._response is None:
                self.process_response()

    def _process_response_json_content(self):
        content = self._response
        # result = content.get('result')
        print(f'Got result: {content}')

    def _process_response_binary_content(self):
        content = self._response
        print(f'Got response: {content!r}')

    def _process_write(self):
        """
        process the write-event
        :return:
        """
        self._event = 'WRITE'
        if not self._request_queued:
            self._queue_request()

        self._write()

        if self._request_queued:
            if not self._send_buffer:
                # Set selector to listen for read events, we're done writing.
                self.set_selector_events_mask('r')

    def _queue_request(self):
        """
        queues up the request to be sent
        :return:
        """
        content = self._request['content']
        content_type = self._request['type']
        content_encoding = self._request['encoding']
        if content_type == 'text/json':
            req = {
                'content_bytes': json_encode(content, content_encoding),
                'content_type': content_type,
                'content_encoding': content_encoding,
            }
        else:
            req = {
                'content_bytes': content,
                'content_type': content_type,
                'content_encoding': content_encoding,
            }
        message = self._create_message(**req)
        self._send_buffer += message
        self._request_queued = True

    def process_response(self):
        content_len = self._jsonheader['content-length']
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self._jsonheader['content-type'] == 'text/json':
            encoding = self._jsonheader['content-encoding']
            self._response = json_decode(data, encoding)
            print(f'Received response {self.response!r} from {self._ipaddr}')
            self._process_response_json_content()
        else:
            # Binary or unknown content-type
            self._response = data
            print(
                f'Received {self._jsonheader["content-type"]} '
                f'response from {self._ipaddr}'
            )
            self._process_response_binary_content()
        # Close when response has been processed
        self.close()
