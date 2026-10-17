import os
from dotenv import load_dotenv

# This file is called config_file instead of simply config
# because Langgraph is already using the name 'config' implicitly.

load_dotenv()

paths = {
    'log_path': './logs/',
    'logger_name': 'ts_logger',
    'log_filename': 'ts_log'
}


llm_param = {
    'openweb_ui_token': os.getenv('openweb_ui_token', ''),
    }
