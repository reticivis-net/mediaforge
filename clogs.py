# configure logging https://coloredlogs.readthedocs.io/en/latest/api.html#id28
import logging

import coloredlogs

import config

logger = logging.getLogger(__name__)
field_styles = {
    'levelname': {'bold': True, 'color': 'blue'},
    'asctime': {'color': 2},
    'filename': {'color': 6},
    'funcName': {'color': 5},
    'lineno': {'color': 13}
}
level_styles = coloredlogs.DEFAULT_LEVEL_STYLES
level_styles['COMMAND'] = {'color': 4}
logging.addLevelName(25, "NOTICE")
logging.addLevelName(35, "SUCCESS")
logging.addLevelName(11, "COMMAND")
loglevel = 25 if config.log_level == "NOTICE" else config.log_level
coloredlogs.install(level=loglevel, fmt='[%(asctime)s] [%(filename)s:%(funcName)s:%(lineno)d] '
                                        '%(levelname)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p', field_styles=field_styles, level_styles=level_styles, logger=logger)
if hasattr(config, "logdiscordpytofile") and config.logdiscordpytofile:
    dlogger = logging.getLogger('nextcord')
    dlogger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w+')
    handler.setFormatter(logging.Formatter('[%(asctime)s] [%(filename)s:%(funcName)s:%(lineno)d] '
                                           '%(levelname)s %(message)s'))
    handler.setLevel(logging.DEBUG)
    dlogger.addHandler(handler)
