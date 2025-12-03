import logging, sys
from config import Config

def main():
    logging.basicConfig(level=Config.LOG_LEVEL)

if __name__ == "__main__":
    main()