"""SoldiSnakeBoterino"""


import io
import json
import random
import selectors
import socket
import struct
import sys
import time
import traceback
import threading



CLOWDERHOST = '127.0.0.1'#"185.104.16.34"
PORT = 65432


class Message:
    """
    constructor for super-class
    """

    def __init__(self, selector, socket, ipaddr):
        self._selector = selector
        self._socket = socket
        self._ipaddr = ipaddr
        self._event = ""
        self._recv_buffer = b""
        self._send_buffer = b""
        self._request = None
        self._jsonheader_len = None
        self._jsonheader = None
        self._response = None
        self._response_created = False

    def process_events(self, mask):
        """
        process the events
        :param mask:
        :return:
        """
        if mask & selectors.EVENT_READ:
            self._process_read()
        if mask & selectors.EVENT_WRITE:
            self._process_write()

    def set_selector_events_mask(self, mode):
        """
        Set selector to listen for events: .
        :param mode: mode is 'r', 'w', or 'rw'
        :return:
        """
        if mode == "r":
            events = selectors.EVENT_READ
        elif mode == "w":
            events = selectors.EVENT_WRITE
        elif mode == "rw":
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f"Invalid events mask mode {mode!r}.")
        self._selector.modify(self._socket, events, data=self)

    def _process_headers(self):
        """
        process the protocol and json headers
        :return:
        """
        self._event = "READ"
        self._read()

        if self._jsonheader_len is None:
            self._process_protoheader()

        if self._jsonheader_len is not None:
            if self._jsonheader is None:
                self._process_jsonheader()

    def _process_read(self):
        """
        dummy implementation must be implemented in the child class
        :return:
        """
        raise NotImplementedError

    def _read(self):
        """
        reads the data from the socket
        :return: None
        """
        try:
            # Should be ready to read
            data = self._socket.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
            else:
                raise RuntimeError("Peer closed.")

    def _create_response_json_content(self):
        content_encoding = "utf-8"
        content = json_encode(self._response, content_encoding)

        response = {
            "content_bytes": content,
            "content_type": "text/json",
            "content_encoding": content_encoding,
        }

        return response

    def _create_response_text_content(self):
        response = {
            "content_bytes": bytes(self._response, "utf-8"),
            "content_type": "text/plain",
            "content_encoding": "utf-8",
        }
        return response

    def _process_write(self):
        """
        dummy implementation must be implemented in the child class
        :return:
        """
        raise NotImplementedError

    def _write(self):
        """
        sends the response to the client
        :return:
        """
        if self._send_buffer:
            print(f"Sending {self._send_buffer!r} to {self._ipaddr}")
            try:
                # Should be ready to write
                sent = self._socket.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # Close when the buffer is drained. The response has been sent.
                if (
                    type(self).__name__ == "ServerMessage"
                    and sent
                    and not self._send_buffer
                ):
                    self.close()

    def _process_protoheader(self):
        """
        process the protocol header
        :return:
        """
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(">H", self._recv_buffer[:hdrlen])[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def _process_jsonheader(self):
        """
        process the json header
        :return:
        """
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader = json_decode(self._recv_buffer[:hdrlen], "utf-8")
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                "byteorder",
                "content-length",
                "content-type",
                "content-encoding",
            ):
                if reqhdr not in self._jsonheader:
                    raise ValueError(f'Missing required header "{reqhdr}".')

    def _create_message(self, *, content_bytes, content_type, content_encoding):
        """
        creates the encoded message to send to the client
        :param content_bytes:
        :param content_type:
        :param content_encoding:
        :return:
        """

        jsonheader = {
            "byteorder": sys.byteorder,
            "content-type": content_type,
            "content-encoding": content_encoding,
            "content-length": len(content_bytes),
        }
        jsonheader_bytes = json_encode(jsonheader, "utf-8")
        message_hdr = struct.pack(">H", len(jsonheader_bytes))

        response_message = message_hdr + jsonheader_bytes + content_bytes
        return response_message

    def close(self):
        print(f"Closing connection to {self._ipaddr}")
        try:
            self._selector.unregister(self._socket)
        except Exception as e:
            print(f"Error: selector.unregister() exception for {self._ipaddr}: {e!r}")

        try:
            self._socket.close()
        except OSError as e:
            print(f"Error: socket.close() exception for {self._ipaddr}: {e!r}")
        finally:
            # Delete reference to socket object for garbage collection
            self._socket = None

    @property
    def ipaddr(self):
        return self._ipaddr

    @ipaddr.setter
    def ipaddr(self, value):
        self._ipaddr = value

    @property
    def event(self):
        return self._event

    @event.setter
    def event(self, value):
        self._event = value

    @property
    def request(self):
        return self._request

    @property
    def response(self):
        return self._response

    @response.setter
    def response(self, value):
        self._response = value


def json_encode(obj, encoding):
    """
    encodes the object as json
    :param obj: the object to encode
    :param encoding: the codec to use for encoding
    :return: String
    """
    return json.dumps(obj, ensure_ascii=False).encode(encoding)


def json_decode(json_bytes, encoding):
    """
    decodes json data into an object
    :param json_bytes: the json data to be decoded
    :param encoding: the codec to use for decoding
    :return: Object
    """
    text_io_wrap = io.TextIOWrapper(
        io.BytesIO(json_bytes), encoding=encoding, newline=""
    )
    obj = json.load(text_io_wrap)
    text_io_wrap.close()
    return obj


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
        print(f"Got result: {content}")

    def _process_response_binary_content(self):
        content = self._response
        print(f"Got response: {content!r}")

    def _process_write(self):
        """
        process the write-event
        :return:
        """
        self._event = "WRITE"
        if not self._request_queued:
            self._queue_request()

        self._write()

        if self._request_queued:
            if not self._send_buffer:
                self.set_selector_events_mask("r")

    def _queue_request(self):
        """
        queues up the request to be sent
        :return:
        """
        content = self._request["content"]
        content_type = self._request["type"]
        content_encoding = self._request["encoding"]
        if content_type == "text/json":
            req = {
                "content_bytes": json_encode(content, content_encoding),
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        else:
            req = {
                "content_bytes": content,
                "content_type": content_type,
                "content_encoding": content_encoding,
            }
        message = self._create_message(**req)
        self._send_buffer += message
        self._request_queued = True

    def process_response(self):
        content_len = self._jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self._jsonheader["content-type"] == "text/json":
            encoding = self._jsonheader["content-encoding"]
            self._response = json_decode(data, encoding)
            print(f"Received response {self.response!r} from {self._ipaddr}")
            self._process_response_json_content()
        else:
            # Binary or unknown content-type
            self._response = data
            print(
                f"Received {self._jsonheader['content-type']} "
                f"response from {self._ipaddr}"
            )
            self._process_response_binary_content()
        # Close when response has been processed
        self.close()


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
        content_len = self._jsonheader["content-length"]
        if not len(self._recv_buffer) >= content_len:
            return
        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        if self._jsonheader["content-type"] == "text/json":
            encoding = self._jsonheader["content-encoding"]
            self._request = json_decode(data, encoding)
            print(f"Received request {self._request!r} from {self._ipaddr}")
        else:
            self._request = data
            print(
                f"Received {self._jsonheader['content-type']} "
                f"request from {self._ipaddr}"
            )

    def _process_write(self):
        """
        process the write-event
        :return:
        """
        self._event = "WRITE"
        if self._request:
            if not self._response_created:
                self._create_response()

        self._write()

    def _create_response(self):
        """
        creates the response to the client
        :return:
        """
        if self._request["action"] == "QUERY":
            data = self._create_response_json_content()
        else:
            data = self._create_response_text_content()
        output = self._create_message(**data)
        self._response_created = True
        self._send_buffer += output

    def _create_response_text_content(self):
        response = {
            "content_bytes": bytes(str(self._response), "utf-8"),
            "content_type": "text/plain",
            "content_encoding": "utf-8",
        }
        return response



def send_request(action):
    """
    sends a request to the server
    :param action:
    :return:
    """
    sel = selectors.DefaultSelector()
    request = create_request(action)
    start_connection(sel, CLOWDERHOST, PORT, request)

    message = None
    try:
        while True:
            events = sel.select(timeout=1)
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print(
                        f"Main: Error: Exception for {message.ipaddr}:\n"
                        f"{traceback.format_exc()}"
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        sel.close()
    if message is not None:
        return message


def create_request(action_item):
    """Create a request to send to the server"""
    return dict(
        type="text/json",
        encoding="utf-8",
        content=action_item,
    )


def start_connection(sel, host, port, request):
    """Create a connection for a request"""
    addr = (host, port)
    print(f"Starting connection to {addr}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = ClientMessage(sel, sock, addr, request)
    sel.register(sock, events, data=message)


# ========== ========== Bot ========== ==========


class SolidSnakeBot:
    """
    This is a helper class to run the bot in the local environment.
    The name MUST match the filename.
    """

    def __init__(self, name):
        self.name = name
        self._bot = SolidSnake(name)

    def request(self, data):
        """
        Request for a response
        :param data:
        :return:
        """
        payload = None
        if isinstance(data, dict):
            payload = data
        else:
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                print("ERROR: JSONDecodeError - payload")
                return "NONE"

        action = payload["action"]
        if action == "PLAY":
            play = self._bot.play()
            return play #{"card": play if play is not None else "NONE"}
        elif action == "START":
            self._bot.start_round(payload)
            return "ACK"
        elif action == "DRAW":
            self._bot.add_card(payload["card"])
            return "ACK"
        elif action == "INFORM":
            self._bot.inform(payload["botname"], payload["event"], payload["data"])
            return "ACK"
        elif action == "DEFUSE":
            pos = self._bot.handle_exploding_kitten(int(payload["decksize"]))
            return pos #{"position": pos}
        elif action == "FUTURE":
            self._bot.see_the_future(payload["cards"])
            return "ACK"
        elif action == "EXPLODE":
            return "ACK"
        return "NONE"


class SolidSnake:
    def __init__(self, name):
        self.name = name
        self._hand = []
        self._strategy = None

    def start_round(self, data):
        pass

    def add_card(self, cardname):
        self._hand.append(cardname)

    def inform(self, botname, action, response):
        self._strategy.inform(botname, action, response)

    def play(self):
        card = self._strategy.play()
        if card and card != "NONE":
            self._hand.pop(self._hand.index(card))
        return card

    def handle_exploding_kitten(self, deck_size):
        return self._strategy.handle_exploding_kitten(deck_size)

    def see_the_future(self, top_three):
        self._strategy.see_the_future(top_three)


def register(local_ip, bot):
    """
    register the bot with the discovery service
    """
    action = {"action": "MEOW", "ip": local_ip, "name": bot.name, "type": "bot"}
    message = send_request(action)

    try:
        port = int(message.response.decode("utf-8").strip())
        print(f"Success! Port: {port}.")
        return port
    except Exception as e:
        print(f"Failed! Response: {e}")
        return None


def send_heartbeat(bot):
    """
    send a heartbeat to the discovery service
    """
    action = {"action": "SWISH", "name": bot.name}
    while True:
        try:
            message = send_request(action)
            print(f"Heartbeat sent for {bot.name}")
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")
        time.sleep(30)


def open_up_port(local_ip, port, bot):
    """
    main entry point for the discovery service
    """
    sel = selectors.DefaultSelector()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Avoid bind() exception: OSError: [Errno 48] Address already in use
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((local_ip, port))
    sock.listen()
    print(f"Listening on {(local_ip, port)}")
    sock.setblocking(False)
    sel.register(sock, selectors.EVENT_READ, data=None)

    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    accept_wrapper(sel, key.fileobj, bot)
                else:
                    message = key.data
                    try:
                        message.process_events(mask)
                        if (
                            message.request is not None
                            and not message._response_created
                        ):
                            print(f"Processing request: {message.request}")
                            response = bot.request(message.request)
                            print(f"Bot response: {response}")
                            response = response if response is not None else "NONE"
                            message.response = (
                                response
                            )
                            message.set_selector_events_mask("w")
                    except Exception:
                        print(
                            f"Main: Error: Exception for {message.ipaddr}:\n"
                            f"{traceback.format_exc()}"
                        )
                        message.close()
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        sel.close()
        try:
            sock.close()
            print("Socket closed")
        except:
            pass


def accept_wrapper(sel, sock, bot):
    """
    accept a connection
    """
    try:
        conn, addr = sock.accept()  # Should be ready to read
        print(f"Accepted connection from {addr}")
        conn.setblocking(False)
        message = ServerMessage(sel, conn, addr)
        sel.register(conn, selectors.EVENT_READ, data=message)
    except Exception as e:
        print(f"Error accepting connection: {e}")


def get_my_ip():
    """..."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect((CLOWDERHOST, 1))
        ip_addr = s.getsockname()[0]
    except:
        ip_addr = "127.0.0.1"
    finally:
        s.close()
    return ip_addr



def main():
    """
    main function for the bot
    :return:
    """

    local_ip = get_my_ip()  # socket.gethostbyname(socket.gethostname())
    bot = SolidSnakeBot("SnakeBot")

    try:
        port = register(local_ip, bot)
        if port is None:
            return

        heart = threading.Thread(target=send_heartbeat, args=(bot,))
        heart.daemon = True
        heart.start()

        open_up_port(local_ip, int(port), bot)
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
