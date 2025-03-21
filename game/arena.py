""" Provides the game arena and the game itself. """
import random
from typing import List

from game.bot import Bot
from game.cards import CardCounts, CardType, Card


class Arena:
    """
    The game arena manages the game itself and the bots in the game.
    """

    def __init__(self):
        self._cardcounts = None
        self._bots_alive = []
        self._ranking = []
        self._deck = None
        self._active_bot = None
        self._queue = ['PLAY']
        self._state = ''

    def start_round(self, bot_count: int) -> CardCounts:
        """
        Initialize the deck and the bots' hands for a new round.
        :param bot_count: the number of bots
        :return: the card counts
        """
        for i in range(bot_count):
            bot = Bot()
            self._bots_alive.append(bot)
        self._cardcounts = CardCounts(
            EXPLODING_KITTEN=bot_count - 1,
            DEFUSE=2,
            SKIP=bot_count + 6,
            SEE_THE_FUTURE=bot_count * 2,
            NORMAL=bot_count * 5,
            SHUFFLE=bot_count + 1
        )
        self.initialize_deck()

        self._active_bot = 0
        return self._cardcounts

    def initialize_deck(self) -> None:
        """
        Initializes the deck with the given card counts
        :return: None
        """
        self._deck = []
        for card_type in CardType:
            if card_type == CardType.EXPLODING_KITTEN:
                continue
            count = getattr(self._cardcounts, card_type.name)
            self._deck.extend([Card(card_type) for _ in range(count)])
        random.shuffle(self._deck)

        self.initialize_bot_hands()

        for _ in range(self._cardcounts.EXPLODING_KITTEN):
            self._deck.insert(random.randint(0, len(self._deck)), Card(CardType.EXPLODING_KITTEN))

    def initialize_bot_hands(self) -> None:
        """
        Initializes the bots' hands
        :return: None
        """
        for bot in self._bots_alive:
            bot.hand.append(Card(CardType.DEFUSE))
        for i in range(7):
            for bot in self._bots_alive:
                card = self._deck.pop()
                bot.hand.append(card)

    def take_turn(self) -> [int, str]:
        """
        Take a turn for the active bot.
        :return:
        - the index of the active bot
        - the action the bot has to take
        - the data to send to the bot
        """
        self._state = self._queue.pop(0)
        if self._state in ['PLAY']:
            return self._active_bot, self._state, None
        elif self._state == 'NEXTBOT':
            self._active_bot = self._next_bot()
            self._queue.append('PLAY')
            return self._active_bot, self._state, None
        elif self._state == 'DRAW':
            card = self._deck.pop()
            cardname = card.card_type.name
            if cardname == 'EXPLODING_KITTEN':
                if Card(CardType.DEFUSE) in self._bots_alive[self._active_bot].hand:
                    self._queue.append('DEFUSE')
                else:
                    self._queue.append('EXPLODE')
                    self._ranking.append(self._active_bot)
            else:
                self._bots_alive[self._active_bot].hand.append(card)
                self._queue.append('NEXTBOT')
            return self._active_bot, self._state, cardname
        elif self._state == 'DEFUSE':
            self._remove_card('DEFUSE')
            self._queue.append('NEXTBOT')
            return self._active_bot, self._state, None
        elif self._state == 'EXPLODE':
            self._bots_alive[self._active_bot].alive = False
            self._queue.append('NEXTBOT')
            return self._active_bot, self._state, None
        elif self._state == 'FUTURE':
            top_three = []
            for i in range(min(3, self.deck_size)):
                top_three.append(self._deck[i].card_type.name)
            self._queue.append('PLAY')
            return self._active_bot, self._state, top_three

    def analyze_turn(self, response) -> bool:
        """
        Analyze the response of the bot.
        :param response: the response of the bot
        :return: True if the response is valid, False otherwise
        """
        bot = self._bots_alive[self._active_bot]
        if self._state == 'PLAY':
            if response.upper() == 'NONE':
                self._queue.append('DRAW')
            elif self._has_card(bot, response):
                self._remove_card(response)
                if response == 'SEE_THE_FUTURE':
                    self._queue.append('FUTURE')
                elif response == 'SHUFFLE':
                    random.shuffle(self._deck)
                    self._queue.append('PLAY')
                elif response == 'SKIP':
                    self._queue.append('NEXTBOT')
                else:
                    self._queue.append('PLAY')
                return True
            else:
                self._queue.append('EXPLODE')
                return False
        elif self._state == 'DEFUSE':
            try:
                position = int(response)
            except ValueError:
                position = -1
            if 0 <= position < len(self._deck):
                self._deck.insert(position, Card(CardType.EXPLODING_KITTEN))
                print (f'Added Exploding Kitten at position {position}')
            else:
                self._deck.append(Card(CardType.EXPLODING_KITTEN))
                print (f'Added Exploding Kitten at the end')
        elif self._state == 'NEXTBOT':
            return False
        return True

    def read_hand(self, active_bot: int) -> List[str]:
        """
        Read the hand of the bot.
        :param active_bot: the index of the bot
        :return: the hand of the bot
        """
        bot = self._bots_alive[active_bot]
        hand = []
        for i in range(len(bot.hand)):
            card = bot.hand[i]
            hand.append(card.card_type.name)

        return hand

    def _has_card(self, bot: Bot, cardname) -> bool:
        """
        Check if the bot has this card.
        :param cardname: the name of the card
        :return: True if the play is legal, False otherwise
        """
        if cardname in bot.hand:
            return True
        return False

    def _remove_card(self, cardname) -> None:
        """
        Remove the card from the bot's hand.
        :param cardname: the name of the card
        :return: None
        """
        bot = self._bots_alive[self._active_bot]
        for i in range(len(bot.hand)):
            if bot.hand[i].card_type.name == cardname:
                bot.hand.pop(i)
                break

    def _next_bot(self) -> int:
        """
        Move to the next bot.
        :return:
        """
        next_bot = (self._active_bot + 1) % len(self._bots_alive)
        while not self._bots_alive[next_bot].alive:
            next_bot = (next_bot + 1) % len(self._bots_alive)
        return next_bot

    @property
    def deck_size(self):
        """ returns the deck size """
        return len(self._deck)
    @property
    def winner(self):
        """ returns the winner """
        # Get the index of the bot with alive = true
        for i in range(len(self._bots_alive)):
            if self._bots_alive[i].alive:
                return i
        return 0

    @property
    def ranking(self):
        """ returns the ranking """
        bot_rank = [self.winner]
        for bot_number in reversed(self._ranking):
            bot_rank.append(bot_number)
        return bot_rank