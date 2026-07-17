import os
from dotenv import load_dotenv

# This file is called config_file instead of simply config
# because Langgraph is already using the name 'config' implicitly.

load_dotenv()

paths = {
    'log_path': './logs/',
    'logger_name': 'ts_logger',
    'log_filename': 'ts_log',
    'data_path': './data/',
    'test_set_filename': 'test_set.csv',
    'car_measur_filename': 'car_measur.csv'
}


llm_param = {
    'model_name': 'mistral-small:24b-instruct-2501-q8_0', #'llama3.2:3b-instruct-q8_0',
    'base_url': "http://sc-030361l.intra.dlr.de:8080/ollama/",  # Alternative API, http://sc-030362l.intra.dlr.de:11434
    'suffix_url_generate': '/api/generate', # "/ollama/api/generate",
    'suffix_url_models': "/api/models",
    #'openweb_ui_token': os.getenv('openweb_ui_token'),
    'openweb_ui_token': "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjI3MWNlZTdhLTFjYTUtNDEzMC04MTNmLTE4MGMwYTg1NTJlNyJ9.qIup7qu2NjUBbVr4jQ4-OHCWffuP1Mgck0UmLnet1Ik",
    'second_fm_endpoint': "http://sc-030362l.intra.dlr.de:11434"
    }