""" Combines the clowder-service and a test-service for the arena """
import threading
from time import sleep

# from arena.arena_test import arena  # Testing the communication without the actual game
from arena.arena_game import arena  # Testing the actual game, you need at least 2 bots
from clowder.clowder_service import clowder

CLOWDERHOST = '127.0.0.1'
CLOWDERPORT = 65432

def main():
    """
    Starts the clowder service and the arena
    :return:
    """
    timer_runs = threading.Event()
    clowder_service = threading.Thread(target=run_clowder, args=(timer_runs,))
    clowder_service.start()

    print (f'Clowder service started on {CLOWDERHOST}:{CLOWDERPORT}')
    print('Press Ctrl+C to stop')
    sleep(2)
    input('Manually start all bots now.\nPress Enter to start the arena\n')

    try:
        while True:
            print('Starting the arena')
            arena_serivce = threading.Thread(target=run_arena)
            arena_serivce.start()
            arena_serivce.join()
            sleep(10)
    except KeyboardInterrupt:
        print('Stopping the arena')
        timer_runs.clear()
        clowder_service.join()

def run_clowder(timer_runs):
    """
    Run the clowder service
    :param timer_runs:
    :return:
    """
    clowder()

def run_arena():
    """
    Run the arena
    :return:
    """
    arena()

if __name__ == '__main__':
    main()