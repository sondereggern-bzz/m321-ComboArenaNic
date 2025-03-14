#!/usr/bin/env python3

import selectors
import socket
import traceback

from common.server_message import ServerMessage
from clowder.kitten_bots import KittenBots


CLOWDERHOST = '127.0.0.1'
CLOWDERPORT = 65432


def clowder():
    sel = selectors.DefaultSelector()
    kitten_bots = KittenBots()

    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Avoid bind() exception: OSError: [Errno 48] Address already in use
    lsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    lsock.bind((CLOWDERHOST, CLOWDERPORT))
    lsock.listen()
    print(f'Listening on {(CLOWDERHOST, CLOWDERPORT)}')
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
                        process_action(message, kitten_bots)
                    except Exception:
                        print(
                            f'Main: Error: Exception for {message.ipaddr}:\n'
                            f'{traceback.format_exc()}'
                        )
                        message.close()
    except KeyboardInterrupt:
        print('Caught keyboard interrupt, exiting')
    finally:
        sel.close()


def process_action(message, kittens):
    print(message.event)
    if message.event == 'READ':
        action = message.request['action']
        if action == 'MEOW':
            service_port = kittens.register(
                message.request['type'],
                message.request['ip'],
                message.request['name']
            )
            message.response = service_port
        elif action == 'SWISH':
            result = kittens.heartbeat(
                message.request['name']
            )
            message.response = result
        elif action == 'QUERY':
            result = kittens.query(
                message.request['type']
            )
            message.response = result
        elif action == 'CATNAP':
            kittens.unregister(
                message.request['name']
            )
            message.response = 'ACK'
        message.set_selector_events_mask('w')


def accept_wrapper(sel, sock):
    conn, addr = sock.accept()  # Should be ready to read
    print(f'Accepted connection from {addr}')
    conn.setblocking(False)
    message = ServerMessage(sel, conn, addr)
    sel.register(conn, selectors.EVENT_READ, data=message)

if __name__ == '__main__':
    pass
