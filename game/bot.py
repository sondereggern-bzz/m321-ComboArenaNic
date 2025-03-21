""" Abstract class for bots. """


class Bot:
    """ Defines the interface for a bot. """

    def __init__(self):
        self._hand = []
        self._alive = True

    @property
    def hand(self):
        """ returns the hand """
        return self._hand

    @hand.setter
    def hand(self, value):
        """ sets the hand """
        self._hand = value

    @property
    def alive(self):
        """ returns the alive """
        return self._alive

    @alive.setter
    def alive(self, value):
        """ sets the alive """
        self._alive = value
