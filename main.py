from bot.async_telebot import TelegramBot
from utils import load_key, setup_logger


def main() -> None:
    if not (BOT_TOKEN := load_key("BOT_TOKEN")):
        raise RuntimeError("Telegram BOT_TOKEN is not set in environment")

    logger = setup_logger('BotMain', 'bot.log')

    telegram_bot = TelegramBot(BOT_TOKEN, logger)

    telegram_bot.run()


if __name__ == "__main__":
    main()
