import re
import asyncio
import os
import sqlite3
import sys
from pathlib import Path
from time import sleep
from dotenv import load_dotenv
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from typing import List
from langchain_core import messages
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit
from langchain_community.utilities.requests import TextRequestsWrapper
from typing import (
    Annotated,
    Sequence,
    TypedDict,
)
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from functools import partial
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import json
from langchain_core.messages import ToolMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
import inspect
from pydantic  import BaseModel, Field
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit, RequestsGetTool
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from IPython.display import Image, display
#import pygraphviz
import time
import pandas as pd
from ament_index_python.packages import get_package_share_directory

ALLOW_DANGEROUS_REQUEST = True

toolkit = RequestsToolkit(
    requests_wrapper=TextRequestsWrapper(headers={}),
    allow_dangerous_requests=ALLOW_DANGEROUS_REQUEST,
)

# Solve the bug where the interactive session and debugger cannot find the imports
working_dir = str(Path(__file__).parent.parent)
sys.path.append(working_dir)
os.chdir(working_dir)

from .misc import config_file
from .misc.logger import logger
from .misc import prompts
from . import agent_framework




class TextToCommandWorkflow:
    def __init__(self, model_name):
        self.model_name = model_name



        self.llm = ChatOllama(base_url="http://localhost:11434", #base_url=config_file.llm_param['base_url'],
                        model=model_name,
                         client_kwargs={'headers':{"Authorization": f"Bearer {config_file.llm_param['openweb_ui_token']}"}})

        # Read car measurements
        self.sep = '$'

        package_share_directory = get_package_share_directory('fm_adore_interface')
        self.car_meas_path = (package_share_directory + "/data/" + config_file.paths['car_measur_filename'])

        if not os.path.isfile(self.car_meas_path):
            raise FileNotFoundError(f"Car measurements file not found: {self.car_meas_path}")

        self.car_meas_df = pd.read_csv(self.car_meas_path, sep=self.sep)


        # try:
        #     self.car_meas_path = config_file.paths['data_path'] + config_file.paths['car_measur_filename']
        #     self.car_meas_df = pd.read_csv(self.car_meas_path, sep='$')
        # except:
        #     config_file.paths['data_path'] = get_package_share_directory('fm_adore_interface') + "/data/"
        #     self.car_meas_path = config_file.paths['data_path'] + config_file.paths['car_measur_filename']
        #     self.car_meas_df = pd.read_csv(self.car_meas_path, sep='$')
       
            

        # Define the graph

        # We remove the classification correction agent,
        # because it turned out to be detrimental for accuracy.

        self.llm_agent = agent_framework.LLMAgent()

        self.workflow = StateGraph(agent_framework.AgentState)
        self.workflow.add_node("get_car_measurement_model", partial(self.llm_agent.get_car_measurement_model, self.llm, self.car_meas_df))
        self.workflow.add_node("decide_branch_model", partial(self.llm_agent.decide_branch_model, self.llm, self.car_meas_df))
        self.workflow.set_entry_point("decide_branch_model")
        self.workflow.add_edge("get_car_measurement_model", END)

        self.workflow.add_conditional_edges(
            "decide_branch_model",
            self.llm_agent.branch_last_msg,
            {
                "1.": "stt_correct_agent",
                "2.": "get_car_measurement_model",
            },
        )

        self.workflow.add_node("classification_agent", partial(self.llm_agent.classification_model, self.llm))
        self.workflow.add_node("stt_correct_agent", partial(self.llm_agent.stt_correct_model, self.llm))
        # workflow.add_node("classification_correct_agent", partial(self.llm_agent.classification_correct_model, self.llm))
        self.workflow.add_edge("stt_correct_agent", "classification_agent")
        #workflow.add_edge("classification_agent", "classification_correct_agent")
        self.workflow.add_edge("classification_agent", END)

    def text_to_command(self, text):
        # Run a new graph
        inputs = {"messages": [("user", text)]}
        config_graph = {"configurable": {"thread_id": "1234"}}
        memory = MemorySaver()
        graph = self.workflow.compile(checkpointer=memory)
        graph.invoke(inputs, config=config_graph)
        answer = graph.get_state(config_graph)[0]['messages'][-1].content
        # Save the answers
        # Keep only the action text. Sometimes the LLM messes up the action numbers.
        answer = re.sub(r'^[\w+:\s]*[0-9]*.\s', '', answer)
        # Remove a possible trailing white space, tab
        answer = re.sub(r'^[\s\t]+$', '', answer)
        return answer # answer should be same as one of the predefined commands
        

# # ########## Test only one command

# # question = "Meine Ausgang ist der dritte im Kreisverkehr."
# question = "Fahr auf dem rechte Streife."
# question = "Continue on this street."

# # Now we can compile and visualize our graph
# memory = MemorySaver()
# graph = workflow.compile(checkpointer=memory)

# try:
#     display(Image(graph.get_graph().draw_png()))
# except Exception:
#     # This requires some extra dependencies and is optional
#     pass

# inputs = {"messages": [("user", question)]}
# config_graph = {"configurable": {"thread_id": "1234"}}
# memory = MemorySaver()
# graph = workflow.compile(checkpointer=memory)
# self.llm_agent.print_stream(graph.stream(inputs, stream_mode="values", config=config_graph))







if __name__ == '__main__':
    #model_name = 'DLR_FM_1.llama3.3:latest'
    model_name = 'llama3.2:latest'
    # model_name = 'DLR_FM_1.llama-pro:latest'
    # model_name = 'DLR_FM_1.llama3.1:8b-instruct-q8_0'
    # model_name = 'DLR_FM_2.llama3.1:8b'
    # model_name = 'DLR_FM_2.mistral-small:24b-instruct-2501-q8_0'
    # model_name = 'DLR_FM_2.mixtral:latest'

    ttcw = TextToCommandWorkflow(model_name)


    ######### Evaluate the graph on the test set #############################

    # Load the test set
    test_set_path = config_file.paths['data_path'] + config_file.paths['test_set_filename']
    # test_set_path = config_file.paths['data_path'] + 'test_set_mistakes.csv'
    test_set_df = pd.read_csv(test_set_path, sep='$')
    test_set_df['prediction'] = ''

    start_time = time.time()

    # Evaluate the prompts.
    is_correct_l = []
    for i in range(len(test_set_df)):
        command = test_set_df['command'][i]
        truth = test_set_df['truth'][i]

        answer = ttcw.text_to_command(command)
        
        # Round the numerical answers, in case we are inferring for the car measurements.
        round_dec = 1
        if agent_framework.is_number(answer):
            answer = round(float(answer), round_dec)
        if agent_framework.is_number(truth):
            truth = round(float(truth), round_dec)

        is_correct = str(answer).lower() in str(truth).lower()
        is_correct_l.append(is_correct)
        test_set_df.loc[i, 'prediction'] = answer
        print('Predicted: ' + command + ' -> ' + str(answer) + '\nTruth: ' + str(truth) + ' -> ' + str(is_correct))

    acc = round(sum(is_correct_l) / len(is_correct_l), 2) * 100
    print("Accuracy: " + str(int(acc)) + "%")

    tot_run_time = round(time.time() - start_time, 1)
    print("Run time: "+ str(round((time.time() - start_time)/len(is_correct_l), 1)))

    incorrect_rows = test_set_df[[not x for x in is_correct_l]]
    print(incorrect_rows)


    # ##########################################################

    # # Probe the execution time of a single query

    # import pandas as pd

    # col_l = ['model']
    # exec_time_df = pd.DataFrame(columns=col_l)

    # i = 0
    # for message in graph.get_state(config_graph)[0]['messages']:
    #     content = message.content
    #     if 'model' in content:
    #         model_name = content.split()[0].rstrip(':')
    #     if message.response_metadata:
    #         metadata = message.response_metadata
    #         if message:
    #             exec_time_df.loc[i, 'model'] = model_name
    #             for k, v in metadata.items():
    #                 if 'duration' in k:
    #                     time_val = round(metadata[k]*1e-9, 2)
    #                     exec_time_df.loc[i, k] = time_val
    #             i += 1
    # print(exec_time_df)