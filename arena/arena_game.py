import json
import selectors
import socket
import sys
import traceback
from datetime import datetime
from typing import List

from common.client_message import ClientMessage
from game.arena import Arena
from game.bot import Bot

LOGFILE = datetime.now().strftime('%Y%m%d%H%M%S')
CLOWDERHOST='127.0.0.1'
CLOWDERPORT=65432
LOGPATH='./logs'

def main():
    """
    runs the arena for the kitten bots
    :return:
    """
    global LOGFILE
    rounds = sys.argv[1] if len(sys.argv) > 1 else 1
    for _ in range(rounds):
        try:
            LOGFILE = datetime.now().strftime('%Y%m%d%H%M%S')
            game_round()
        except Exception as e:
            pass
        finally:
            #input('Press Enter to continue...')
            pass
    pass


def game_round():
    """
    Run a game round
    :return:
    """
    bot_list = request_bots()
    log_game('Game', 'START', ','.join([bot['name'] for bot in bot_list]))
    alive_count = len(bot_list)
    arena = Arena()
    start_round(arena, bot_list)
    print('----------- Game Start -----------')
    save_bot = -1
    while alive_count > 1:
        bot_number, action, data = arena.take_turn()
        active_bot = bot_list[bot_number]
        if bot_number != save_bot:
            print(f'Active bot: {active_bot["name"]}')
            save_bot = bot_number
        print(f'  - Action={action} / Data={data}')
        if action == 'PLAY':
            response = send_request(active_bot['ip'], active_bot['port'], {'action': action})
            inform_bots(active_bot['name'], bot_list, 'PLAY', response)
            log_game(active_bot['name'], action, response)
        elif action == 'DRAW':
            log_game(active_bot['name'], action, data)
            if data == 'EXPLODING_KITTEN':
                response = None
            else:
                response = send_request(active_bot['ip'], active_bot['port'],
                                        {'action': 'DRAW', 'card': data})
                inform_bots(active_bot['name'], bot_list, 'DRAW', '')
            print(f'=> {arena.read_hand(bot_number)}')
        elif action == 'DEFUSE':
            response = send_request(active_bot['ip'], active_bot['port'],
                                    {'action': 'DEFUSE', 'decksize': arena.deck_size})
            print(f'  => Bot {active_bot["name"]} defused the exploding kitten')
            log_game(active_bot['name'], action, response)
            inform_bots(active_bot['name'], bot_list, 'DEFUSE', '')
        elif action == 'EXPLODE':
            response = send_request(active_bot['ip'], active_bot['port'], {'action': 'EXPLODE'})
            print(f'  => Bot {active_bot["name"]} exploded')
            log_game(active_bot['name'], action, '')
            alive_count -= 1
            inform_bots(active_bot['name'], bot_list, 'EXPLODE', '')
        elif action == 'FUTURE':
            response = send_request(active_bot['ip'], active_bot['port'],
                                    {'action': 'FUTURE', 'cards': data})
            log_game(active_bot['name'], action, data)
        elif action == 'NEXTBOT':
            response = None
            # input('Press Enter to continue...')
        print(f'  - Response={response}')
        arena.analyze_turn(response)

    finish_round(bot_list, arena)
    pass


def start_round(arena, bot_list):
    """
    Start a new round.
    :param arena:
    :param bot_list:
    :return:
    """
    card_counts = arena.start_round(len(bot_list))
    give_cards(arena, bot_list)
    data = {
        'action': 'START',
        'card_counts': [],
        'bots': [bot['name'] for bot in bot_list],
    }
    for card in dir(card_counts):
        if not card.startswith('__'):
            data['card_counts'].append(
                {
                    'name': card,
                    'count': getattr(card_counts, card),
                }
            )

    ''' Inform all the bots that the round has started. '''
    for bot in bot_list:
        send_request(bot['ip'], bot['port'], data)


def finish_round(bot_list: List[Bot], arena: Arena) -> None:
    """
    Finish the round.
    :param bot_list: List of Bot objects
    :param arena: Arena object
    :return: None
    """
    print('----------- Game Over -----------')

    ranking = []
    rank = 1
    log_game('Game', 'OVER', '')
    for bot_number in arena.ranking:
        print(f'{rank}. {bot_list[bot_number]["name"]}')
        log_game(f'{rank}.', f'{bot_list[bot_number]["name"]}', '')
        ranking.append(bot_list[bot_number]['name'])
        rank += 1

    ''' Inform all the bots that the round has ended. '''
    for bot in bot_list:
        send_request(bot['ip'], bot['port'], {'action': 'OVER', 'ranks': ranking})


def inform_bots(botname, bot_list: List[Bot], action: str, response: str) -> None:
    """
    Inform all the bots of the action that just occurred.
    :param botname: str The name of the bot who took the action
    :param bot_list: List of Bot objects
    :param action: str action
    :param response: str the response from the bot
    :return: None
    """

    for bot in bot_list:
        data = {
            'action': 'INFORM',
            'botname': botname,
            'event': action,
            'data': response,
        }

        send_request(bot['ip'], bot['port'], data)


def give_cards(arena: Arena, bot_list: List) -> None:
    """
    Give cards to the bots in the list.
    :param arena: Arena object
    :param bot_list: List of Bot objects
    :return: None
    """
    active_bot = 0
    for bot in bot_list:
        hand = arena.read_hand(active_bot)
        for card in hand:
            response = send_request(bot['ip'], bot['port'], {'action': 'DRAW', 'card': card})
            log_game(bot['name'], 'DRAW', card)
        active_bot += 1


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
    # print(f'Starting connection to {addr}')
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
    try:
        if action['action'] == 'QUERY':
            bots_json = message.response
            print(f'List of bots: {bots_json}')
            bots = json.loads(bots_json.replace("'", '"'))
            return bots
        elif action['action'] in ['PLAY', 'DEFUSE']:
            return message.response.decode('utf-8')
    except Exception:
        print(f'Error: {traceback.format_exc()}')
        return None


def log_game(botname: str, action: str, response: str) -> None:
    """
    Log the game actions
    :param botname:
    :param action:
    :param response:
    :return:
    """
    entry = {
        'action': action,
        'botname': botname,
        'response': response,
    }
    line = f'{botname} / {action} / {response}'
    logpath = LOGPATH
    with open(f'{logpath}/{LOGFILE}.log', 'a') as logfile:
        logfile.write(f'{line}\n')
    with open(f'{logpath}/{LOGFILE}.json', 'a') as logfile:
        logfile.write(f'{json.dumps(entry)}\n')

if __name__ == '__main__':
    main()
