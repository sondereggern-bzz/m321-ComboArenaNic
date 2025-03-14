from common.message import Message, json_decode


class ServerMessage(Message):
    def __init__(self, selector, socket, ipaddr):
        super().__init__(selector, socket, ipaddr)
        self._response = None
        self._response_created = False

    def _process_read(self):
        """
        process read-event
        :return:
        """
        self._process_headers()

        if self._jsonheader:
            if self._request is None:
                self._process_request()

    def _process_request(self):
        """
        process the request
        :return:
        """
        content_len = self._jsonheader['content-length']
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self._jsonheader['content-type'] == 'text/json':
            encoding = self._jsonheader['content-encoding']
            self._request = json_decode(data, encoding)
            print(f'Received request {self._request!r} from {self._ipaddr}')
        else:
            self._request = data
            print(
                f"Received {self._jsonheader['content-type']} "
                f'request from {self._ipaddr}'
            )

    def _process_write(self):
        """
        process the write-event
        :return:
        """
        self._event = 'WRITE'
        if self._request:
            if not self._response_created:
                self._create_response()

        self._write()

    def _create_response(self):
        """
        creates the response to the client
        :return:
        """
        if self._request['action'] == 'QUERY':
            data = self._create_response_json_content()
        else:
            data = self._create_response_text_content()
        output = self._create_message(**data)
        self.response_created = True
        self._send_buffer += output
