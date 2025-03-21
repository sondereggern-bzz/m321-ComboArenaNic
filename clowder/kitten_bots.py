""" Provides the KittenBots class. """
from datetime import datetime
import random


class KittenBots:
    """
    A class to represent a group of kitten bots.
    """
    def __init__(self):
        """
        Initialize the KittenBots class.
        :param bots: list of bots
        """
        self._bots = []

    def register(self, type: str, hostaddr: str, name: str):
        """
        Register a bot
        :param type:
        :param hostaddr:
        :param name:
        :return:
        """
        for bot in self._bots:
            if bot['name'] == name:
                self.heartbeat(name)
                return bot['port']

        new_service = {
            'service_type': type,
            'ip': hostaddr,
            'port': str(random.randint(60100, 60999)),
            'name': name,
            'heartbeat': datetime.now()
        }
        self._bots.append(new_service)
        return new_service['port']
    
    def heartbeat(self, name):
        """
        Heartbeat for a service.
        :param name:
        :return:
        """
        for service in self._bots:
            if service['name'] == name:
                service['heartbeat'] = datetime.now()
                return 'OK'
        return 'NOT FOUND'
    
    def query(self, service_type: str) -> str:
        """
        Query the kittens for all kittens of a given type.
        :param service_type:
        :return:
        """
        results = []
        for index, service in enumerate(self._bots):
            age = (datetime.now() - service['heartbeat']).total_seconds()
            if age > 5000:
                self._bots.pop(index)
            elif service['service_type'] == service_type:
                results.append(
                    {
                        'ip': service['ip'],
                        'port': service['port'],
                        'name': service['name']
                    }
                )
        return str(results)

    def unregister(self, name: str) -> None:
        """
        Unregister a service.
        :param name:
        :return:
        """
        for index, service in enumerate(self._bots):
            if service['name'] == name:
                self._bots.pop(index)
                return
        return 'NOTFOUND'