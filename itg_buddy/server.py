import os
from discord.utils import setup_logging
from dotenv import load_dotenv
from itg_buddy.bot import ItgBuddy


def main():
    # Load API Key from environment variables in .env
    load_dotenv()
    discord_key = os.getenv("DISCORD_API_KEY")
    if not discord_key or discord_key == "your_discord_api_key_goes_here":
        print("Discord API Key not found.")
        print("Please set the DISCORD_API_KEY or include it in a .env file")
        exit(1)
    setup_logging()
    bot = ItgBuddy()
    bot.run(discord_key, log_handler=None)


if __name__ == "__main__":
    main()
