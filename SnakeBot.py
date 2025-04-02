import io
import json
import selectors
import struct
import sys
import traceback
import socket
import typing



CLOWDERHOST = '127.0.0.1'
CLOWDERPORT = 65432


def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    try:
        s.connect((CLOWDERHOST, 1))
        ip_addr = s.getsockname()[0]
    except Exception:
        ip_addr = '127.0.0.1'
    finally:
        s.close()
    return ip_addr


IPAddr = get_my_ip()



""" Provides the Message class for the server and client classes to inherit from. """



class Message:
    """
    constructor for super-class
    """
    def __init__(self, selector, socket, ipaddr):
        self._selector = selector
        self._socket = socket
        self._ipaddr = ipaddr
        self._event = ''
        self._recv_buffer = b''
        self._send_buffer = b''
        self._request = None
        self._jsonheader_len = None
        self._jsonheader = None

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
        if mode == 'r':
            events = selectors.EVENT_READ
        elif mode == 'w':
            events = selectors.EVENT_WRITE
        elif mode == 'rw':
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
        else:
            raise ValueError(f'Invalid events mask mode {mode!r}.')
        self._selector.modify(self._socket, events, data=self)

    def _process_headers(self):
        """
        process the protocol and json headers
        :return:
        """
        self._event = 'READ'
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
                raise RuntimeError('Peer closed.')

    def _create_response_json_content(self):
        content_encoding = 'utf-8'
        content = json_encode(self._response, content_encoding)

        response = {
            'content_bytes': content,
            'content_type': 'text/json',
            'content_encoding': content_encoding,
        }

        return response

    def _create_response_text_content(self):
        """
        creates the response content as text
        :return: dict
        """
        response = {
            'content_bytes': bytes(self._response, 'utf-8'),
            'content_type': 'text/plain',
            'content_encoding': 'utf-8',
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
            print(f'Sending {self._send_buffer!r} to {self._ipaddr}')
            try:
                # Should be ready to write
                sent = self._socket.send(self._send_buffer)
            except BlockingIOError:
                # Resource temporarily unavailable (errno EWOULDBLOCK)
                pass
            else:
                self._send_buffer = self._send_buffer[sent:]
                # Close when the buffer is drained. The response has been sent.
                if type(self).__name__ == 'ServerMessage' and \
                        sent and \
                        not self._send_buffer:
                    self._close()

    def _process_protoheader(self):
        """
        process the protocol header
        :return:
        """
        hdrlen = 2
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader_len = struct.unpack(
                '>H', self._recv_buffer[:hdrlen]
            )[0]
            self._recv_buffer = self._recv_buffer[hdrlen:]

    def _process_jsonheader(self):
        """
        process the json header
        :return:
        """
        hdrlen = self._jsonheader_len
        if len(self._recv_buffer) >= hdrlen:
            self._jsonheader = json_decode(
                self._recv_buffer[:hdrlen], 'utf-8'
            )
            self._recv_buffer = self._recv_buffer[hdrlen:]
            for reqhdr in (
                    'byteorder',
                    'content-length',
                    'content-type',
                    'content-encoding',
            ):
                if reqhdr not in self._jsonheader:
                    raise ValueError(f'Missing required header "{reqhdr}".')

    def _create_message(
            self,
            *,
            content_bytes,
            content_type,
            content_encoding
    ):
        """
        creates the encoded message to send to the client
        :param content_bytes:
        :param content_type:
        :param content_encoding:
        :return:
        """

        jsonheader = {
            'byteorder': sys.byteorder,
            'content-type': content_type,
            'content-encoding': content_encoding,
            'content-length': len(content_bytes),
        }
        jsonheader_bytes = json_encode(jsonheader, 'utf-8')
        message_hdr = struct.pack('>H', len(jsonheader_bytes))

        response_message = message_hdr + jsonheader_bytes + content_bytes
        return response_message

    def _close(self):
        """
        closes the connection
        """
        print(f'Closing connection to {self._ipaddr}')
        try:
            self._selector.unregister(self._socket)
        except Exception as e:
            print(
                f'Error: selector.unregister() exception for '
                f'{self._ipaddr}: {e!r}'
            )

        try:
            self._socket.close()
        except OSError as e:
            print(f'Error: socket.close() exception for {self._ipaddr}: {e!r}')
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
        io.BytesIO(json_bytes), encoding=encoding, newline=''
    )
    obj = json.load(text_io_wrap)
    text_io_wrap.close()
    return obj




def main():
    bot = TemplateBot("TemplateBot")
    item = {"action": "MEOW", "ip": IPAddr, "name": "SolidSnake_cat", "type": "bot"}

    my_port = send_request(item)  # Captures the returned port
    if my_port is None:
        print("Error: Port was not successfully received.")
        return

    print(f'myport: {my_port}')
    open_port(bot, my_port)  # my_port is passed directly


def process_response(action, message):
    if action['action'] == 'MEOW':
        if hasattr(message, 'response') and isinstance(message.response, bytes):
            my_port = int(message.response.decode('utf-8').strip())
            return my_port
        else:
            print("Error: Response data is missing or invalid.")
            return None




    # register the bot with the clowder => you get a port number
    # open a socket with the port number
        # listen for incoming connections from the arena
        # analyse the incoming connections
        # call the relevant bot method depending on the action
        # send the response back to the arena

def send_request(action):
    sel = selectors.DefaultSelector()
    request = create_request(action)
    start_connection(sel, CLOWDERHOST, CLOWDERPORT, request)

    try:
        while True:
            events = sel.select()
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print(f'{traceback.format_exc()}')

            if not sel.get_map():  # Exit loop when all sockets are closed
                break
    except KeyboardInterrupt:
        print('Caught keyboard interrupt, exiting')
    finally:
        sel.close()

    return process_response(action, message)



def create_request(action_item):
    return dict(
    type='text/json',
    encoding='utf-8',
    content=action_item
)


def start_connection(sel, host, port, request):
    addr = (host, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)

    # Verify the connection status
    result = sock.connect_ex(addr)
    if result != 0:  # Non-zero means connection failed
        print(f"❌ Error: Unable to connect to {addr}. Error code: {result}")
        return  # Exit early if connection fails

    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = ClientMessage(sel, sock, addr, request)
    sel.register(sock, events, data=message)




class ClientMessage(Message):
    """
    constructor for ClientMessage
    """
    def __init__(self, selector, socket, ipaddr, request):
        """
        constructor for the ClientMessage class
        """
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
        """
        process the response content
        :return:
        """
        content = self._response
        print(f'Got result: {content}')

    def _process_response_binary_content(self):
        """
        process binary content in the response
        :return:
        """
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
        """
        Process the response from the server
        :return:
        """
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
        self._close()


def open_port(bot, myport):
    if not isinstance(myport, int) or myport <= 0:
        print("Error: Invalid port value. Cannot open socket.")
        return  # Avoid continuing with invalid data

    sel = selectors.DefaultSelector()

    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        lsock.bind((IPAddr, myport))
    except Exception as e:
        print(f"Error: Failed to bind socket on port {myport}. {e}")
        return

    lsock.listen()
    print(f'Listening on {(IPAddr, myport)}')
    lsock.setblocking(False)
    sel.register(lsock, selectors.EVENT_READ, data=None)

    try:
        while True:
            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    accept_wrapper(sel, key.fileobj)
                else:
                    message = key.data
                    try:
                        message.process_events(mask)
                        response = bot.request(message.request)
                        message.response = response
                        message.set_selector_events_mask('w')
                    except Exception:
                        print(
                            f'Main: Error: Exception for {message.ipaddr}:\n'
                            f'{traceback.format_exc()}'
                        )
                        message._close()
    except KeyboardInterrupt:
        print('Caught keyboard interrupt, exiting')
    finally:
        sel.close()


def process_action(message, services):
    """
    process the action from the client
    :param message: the message object
    :param services: the services object
    """

    if message.event == 'READ':
        action = message.request['action']
        # TODO call the methods on the Services-object depending on the action
        if action == 'register':
            message.response = services.register(message.request['type'], message.request['ip'],
                                                 message.request['port'])
        elif action == 'heartbeat':
            message.response = services.heartbeat(message.request['uuid'])
        elif action == 'query':
            message.response = services.query(message.request['type'])

        message.set_selector_events_mask('w')


def accept_wrapper(sel, sock):
    conn, addr = sock.accept()
    print(f'Accepted connection from {addr}')
    conn.setblocking(False)
    message = ServerMessage(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)



class ServerMessage(Message):
    """
    Class for the message from the server
    """
    def __init__(self, selector, socket, ipaddr):
        """
        constructor for the ServerMessage class
        """
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
        if self._request['action'] == 'query':
            data = self._create_response_json_content()
        else:
            data = self._create_response_text_content()
        output = self._create_message(**data)
        self.response_created = True
        self._send_buffer += output

""" Provides the Message class for the server and client classes to inherit from. """

class TemplateBot():
    """
    Dieser Bot agiert im verteilten System und kommuniziert mit den Services.
    """

    def __init__(self, name):
        self.name = name
        self._bot = TemplateKitten(name)

    def request(self, data):
        """
        Verarbeitet die Anfragen und leitet sie an den internen Bot weiter.
        """
        payload = json.loads(data)
        action = payload['action']
        if action == 'START':
            return self._bot.start_round(payload)
        elif action == 'PLAY':
            # Speichere zusätzliche Parameter für die Spielstrategie
            self._bot._last_bots = payload.get('bots', 0)
            self._bot._last_deck = payload.get('deck', 0)
            return self._bot.play()
        elif action == 'DRAW':
            return self._bot.add_card(payload['card'])
        elif action == 'INFORM':
            return self._bot.inform(payload['botname'], payload['event'], payload['data'])
        elif action == 'DEFUSE':
            return self._bot.handle_exploding_kitten(payload['decksize'])
        elif action == 'FUTURE':
            return self._bot.see_the_future(payload['cards'])
        # Weitere Aktionen können hier ergänzt werden
        return None


class TemplateKitten:
    def __init__(self, name):
        self.name = name
        self._hand = []
        self._future_cards = None
        self._card_counts = {}

    def start_round(self, data):
        """
        Zu Beginn einer Spielrunde werden Hand und Informationen zurückgesetzt.
        """
        self._hand = []
        self._future_cards = None
        if 'card_counts' in data:
            # Speichere die ursprünglichen Kartenanzahlen in einem Dictionary
            self._card_counts = {card['name']: card['count'] for card in data['card_counts']}
        return "ACK"

    def add_card(self, cardname):
        """
        Eine gezogene Karte wird der Hand hinzugefügt und die bekannten Kartenanzahlen werden aktualisiert.
        """
        self._hand.append(cardname)
        if self._card_counts.get(cardname, None) is not None:
            # Reduziere den Zähler der bekannten Karten (aber niemals unter 0)
            self._card_counts[cardname] = max(0, self._card_counts[cardname] - 1)
        return "ACK"

    def play(self):
        """
        Strategische Entscheidung im eigenen Zug:
          - Wenn zukünftige Karten bekannt sind und ein EXPLODING_KITTEN dabei ist, spiele SKIP oder SHUFFLE.
          - Falls keine Zukunftsinformation vorliegt, wird zuerst SEE_THE_FUTURE gespielt, um Informationen zu sammeln.
          - Zusätzlich wird das Risiko basierend auf der bekannten Anzahl an EXPLODING_KITTEN im Verhältnis zur Deckgröße bewertet.
        """
        # Nutze die gespeicherten Informationen zur Deckgröße und verbleibenden Bots
        deck = getattr(self, "_last_deck", 0)
        bots = getattr(self, "_last_bots", 0)

        # Strategie: Falls wir bereits "See the Future" genutzt haben
        if self._future_cards is not None:
            if "EXPLODING_KITTEN" in self._future_cards:
                # Gefährliche Zukunft: Vorzugsweise mit SKIP absichern
                if "SKIP" in self._hand:
                    self._hand.remove("SKIP")
                    self._future_cards = None  # Zurücksetzen
                    return "SKIP"
                # Alternativ: Mit SHUFFLE das Risiko verringern
                elif "SHUFFLE" in self._hand:
                    self._hand.remove("SHUFFLE")
                    self._future_cards = None
                    return "SHUFFLE"
            # Wenn die Zukunft sicher erscheint, spiele keine weiteren Karten
            self._future_cards = None
            return "NONE"

        # Wenn keine Zukunftsinformation vorliegt, spiele SEE_THE_FUTURE, falls vorhanden
        if "SEE_THE_FUTURE" in self._hand:
            self._hand.remove("SEE_THE_FUTURE")
            return "SEE_THE_FUTURE"

        # Falls weiterhin keine Information vorliegt: Risikoabschätzung mit den bekannten Kartenanzahlen
        risk = 0
        if deck > 0 and self._card_counts:
            exploding_remaining = self._card_counts.get("EXPLODING_KITTEN", 0)
            risk = exploding_remaining / deck  # Einfaches Risiko-Modell

        # Bei hohem Risiko (>20%) den Zug absichern, wenn möglich
        if risk > 0.2:
            if "SKIP" in self._hand:
                self._hand.remove("SKIP")
                return "SKIP"
            elif "SHUFFLE" in self._hand:
                self._hand.remove("SHUFFLE")
                return "SHUFFLE"
        # Ansonsten keine Karte spielen
        return "NONE"

    def handle_exploding_kitten(self, deck_size):
        """
        Beim Ziehen eines Exploding Kitten wird diese automatisch entschärft.
        Der Bot platziert das Exploding Kitten am besten ganz unten im Stapel.
        """
        # Platziere an der letzten möglichen Position
        return deck_size - 1

    def see_the_future(self, top_three):
        """
        Speichert die nächsten drei Karten, damit diese Information im nächsten Zug zur Entscheidungsfindung genutzt werden kann.
        """
        self._future_cards = top_three
        return "ACK"

    def inform(self, botname, action, response):
        """
        Aktualisiert die internen Informationen, wenn andere Bots Karten spielen oder ziehen.
        Eigene Aktionen werden dabei ignoriert.
        """
        if botname == self.name:
            return "ACK"

        # Aktualisiere die bekannten Kartenanzahlen, basierend auf den Aktionen anderer
        if action == "PLAY" and response:
            if response in self._card_counts:
                self._card_counts[response] = max(0, self._card_counts[response] - 1)
        elif action == "DRAW" and response and response != "null":
            if response in self._card_counts:
                self._card_counts[response] = max(0, self._card_counts[response] - 1)
        return "ACK"

if __name__ == '__main__':
    main()