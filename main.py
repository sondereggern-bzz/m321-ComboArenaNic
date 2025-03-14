""" Combines the clowder-service and a test-service for the arena """
import threading
from time import sleep

from arena.arena_test import arena
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
    print('Start all bots now. Test arena will start every 10 seconds')

    try:
        while True:
            sleep(10)
            print('Starting the arena')
            arena_serivce = threading.Thread(target=run_arena)
            arena_serivce.start()
            arena_serivce.join()
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