import json
import random
import selectors
import socket
import traceback

from common.client_message import ClientMessage

CLOWDERHOST = '127.0.0.1'
CLOWDERPORT = 65432

def arena():
    """
    runs the arena for the kitten bots
    :return:
    """
    bot_list = request_bots()
    test_messages(bot_list)
    pass


def test_messages(bot_list):
    actions = [
        {
            'card_counts': [
                {'name': 'DEFUSE', 'count': 2},
                {'name': 'EXPLODING_KITTEN', 'count': 1},
                {'name': 'NORMAL', 'count': 10},
                {'name': 'SEE_THE_FUTURE', 'count': 4},
                {'name': 'SHUFFLE', 'count': 3},
                {'name': 'SKIP', 'count': 8}
            ],
            'bots': [
                'cutekitty',
                'randombot'
            ],
            'action': 'START'
        },
        {'card': random_card(), 'action': 'DRAW'},
        {'action': 'PLAY'},
        {'botname': 'cutekitty', 'event': 'PLAY', 'data': random_card(), 'action': 'INFORM'},
        {'botname': 'cutekitty', 'event': 'DRAW', 'data': 'null', 'action': 'INFORM'},
        {'decksize': '3', 'action': 'DEFUSE'},
        {'cards': ['EXPLODING_KITTEN', 'SEE_THE_FUTURE', 'NORMAL'], 'action': 'FUTURE'},
        {'action': 'EXPLODE'},
        {'ranks': ['cutekitty', 'randombot'], 'action': 'GAMEOVER'}
    ]

    for action in actions:
        for bot in bot_list:
            send_request(bot['ip'], bot['port'], action)


def request_bots():
    """
    Request the bots
    :return:
    """

    action = {'action': 'QUERY', 'type': 'bot'}
    response = send_request(CLOWDERHOST, CLOWDERPORT, action)
    return response


def send_request(ipaddr, port, action):
    """
    Send a request to the server
    :param ipaddr:
    :param port:
    :param action:
    :return:
    """

    if type(port) == str:
        port = int(port)
    sel = selectors.DefaultSelector()
    request = create_request(action)
    start_connection(sel, ipaddr, port, request)

    try:
        while True:
            events = sel.select(timeout=60)
            for key, mask in events:
                message = key.data
                try:
                    message.process_events(mask)
                except Exception:
                    print(
                        f'Main: Error: Exception for {message.ipaddr}:\n'
                        f'{traceback.format_exc()}'
                    )
                    message.close()
            # Check for a socket being monitored to continue.
            if not sel.get_map():
                break
    except KeyboardInterrupt:
        print('Caught keyboard interrupt, exiting')
    finally:
        sel.close()
    return process_response(action, message)


def create_request(action_item):
    """
    Create the request
    :param action_item:
    :return:
    """
    return dict(
        type='text/json',
        encoding='utf-8',
        content=action_item,
    )


def start_connection(sel, host, port, request):
    """
    Start the connection to the server
    :param sel:
    :param host:
    :param port:
    :param request:
    :return:
    """
    addr = (host, port)
    print(f'Starting connection to {addr}')
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.connect_ex(addr)
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    message = ClientMessage(sel, sock, addr, request)
    sel.register(sock, events, data=message)


def process_response(action, message):
    """
    process the response from the server
    :param action:
    :param message:
    :return: port
    """
    if action['action'] == 'QUERY':
        bots_json = message.response  # .decode('utf-8')
        print(f'List of bots: {bots_json}')
        bots = json.loads(bots_json.replace("'", '"'))
        return bots


def random_card():
    """
    Select a random card
    :return:
    """
    cards = ['DEFUSE', 'EXPLODING_KITTEN', 'NORMAL', 'SEE_THE_FUTURE', 'SHUFFLE', 'SKIP']
    return cards[random.randint(0, 5)]


if __name__ == '__main__':
    pass
