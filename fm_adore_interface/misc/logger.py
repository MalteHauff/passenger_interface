
import logging
from pathlib import Path

from . import config_file

class Logger():
    """
    Create a logger with debug level to a log file, and info level to the console.
    """
    
    _logger = None
    
    def __init__(self):
        if self._logger is None:
           self.setup_logger()
          
    @property
    def logger(self):
        return self._logger
    
    # Set up the logger
    def setup_logger(self):
        """
        Create a logger with debug level to a log file, and info level to the console.
        """
        
        logger = logging.getLogger(str(Path(config_file.paths['log_path']) / config_file.paths['logger_name']))
        logger.setLevel(logging.DEBUG)
        
        logger.propagate = True
        
        # File handler to write log to a file
        file_handler = logging.FileHandler(str(Path(config_file.paths['log_path']) / config_file.paths['log_filename']))
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler to print logs to the console
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # Log format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to the logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        self._logger = logger

Path(config_file.paths['log_path']).mkdir(exist_ok=True)
logger = Logger()
logger = logger.logger