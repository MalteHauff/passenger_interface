import re
import asyncio
import os
import sqlite3
import sys
from pathlib import Path
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
from pydantic import BaseModel, Field
from langchain_community.agent_toolkits.openapi.toolkit import RequestsToolkit, RequestsGetTool
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from IPython.display import Image, display
#import pygraphviz

from .misc.logger import logger
from .misc import prompts

def is_number(s):
    """ Returns True if string is a number, false otherwise. """
    try:
        float(s)
        return True
    except ValueError:
        return False

class AgentState(TypedDict):
    """The state of the agent."""
    
    messages: Annotated[Sequence[BaseMessage], add_messages]
class LLMAgent():
    
    @staticmethod
    def stt_correct_model(
        llm,
        state: AgentState,
        config: RunnableConfig,
    ):
        """
        Create a correction agent.
        The agent will correct the text of the input command if necessary.
        

        Args:
            llm: the llm to use.
            state: the current state
            config: the Langgraph config       
            
        returns:
            The dictionary with the new messages.
        """
    
        system_prompt = SystemMessage(
            prompts.correction_prompt.format(command_txt=state["messages"][0].content)
        )
        
        response = llm.invoke(system_prompt.content, config)
        # print(response.content)
        # Add the agent name to the message
        response.content = f"{inspect.currentframe().f_code.co_name}: " + response.content
        
        return {"messages": [response]}
    
    @staticmethod
    def classification_model(
        llm,
        state: AgentState,
        config: RunnableConfig,
    ):
        """
        Classify the command into an action.
        

        Args:
            llm: the llm to use.
            state: the current state
            config: the Langgraph config       
            
        returns:
            The dictionary with the new messages.
        """
    
        prompt = SystemMessage(
            prompts.classification_prompt.format(car_actions_l=prompts.car_actions_l, command_txt=state["messages"][0].content)
        )
        
        response = llm.invoke(prompt.content, config)
        # print(response.content)
        # Add the agent name to the message
        response.content = f"{inspect.currentframe().f_code.co_name}: " + response.content
        
        return {"messages": [response]}

    @staticmethod
    def classification_correct_model(
        llm,
        state: AgentState,
        config: RunnableConfig,
    ):
        """
        Correct the output of the classification if needed.
        
        Args:
            llm: the llm to use.
            state: the current state
            config: the Langgraph config       
            
        returns:
            The dictionary with the new messages.
        """
    
        prompt = SystemMessage(
            prompts.classif_correct_prompt.format(car_actions_l=prompts.car_actions_l,
                                                 command_txt=state["messages"][0].content,
                                                 prediction_text=state["messages"][-1].content)
        )

        response = llm.invoke(prompt.content, config)
        # Add the agent name to the message
        response.content = f"{inspect.currentframe().f_code.co_name}: " + response.content
        
        return {"messages": [response]}
    
    @staticmethod
    def get_car_measurement_model(
        llm,
        car_meas_df,
        state: AgentState,
        config: RunnableConfig,
    ):
        """
        Agent to fetch the car measurement (eg speed) from a dataframe.
        
        Args:
            llm: the llm to use.
            car_meas_df: the Pandas dataframe with the car measurements
            state: the current state
            config: the Langgraph config       
            
        returns:
            The dictionary with the new messages.
        """
    
        prompt = SystemMessage(
            prompts.car_prompt.format(
                                    question=state["messages"][0].content,
                                    df=car_meas_df.to_string()
            )
        )

        response = llm.invoke(prompt.content, config)
        # Add the agent name to the message
        response.content = f"{inspect.currentframe().f_code.co_name}: " + response.content
        
        return {"messages": [response]}

    @staticmethod
    def decide_branch_model(
        llm,
        car_meas_df,
        state: AgentState,
        config: RunnableConfig,
    ):
        
        
        """
        There are 2 use cases:
        - classify a command into action
        - return a car measurement
        This LLM decide which use case is relevant.
        
        Args:
            llm: the llm to use.
            car_meas_df: the Pandas dataframe with the car measurements
            state: the current state
            config: the Langgraph config       
            
        returns:
            The dictionary with the new messages.
        """
              
        prompt = SystemMessage(
            prompts.decide_branch_prompt.format(
                                    car_action_l=prompts.car_actions_l,
                                    question=state["messages"][0].content,
                                    df=car_meas_df.to_string()
            )
        )

        response = llm.invoke(prompt.content, config)
        # print(response.content)
        # Add the agent name to the message
        response.content = f"{inspect.currentframe().f_code.co_name}: " + response.content
        
        return {"messages": [response]}
    
    @staticmethod
    def branch_last_msg(state: AgentState):
        """
        Check if the `decide_branch_model` has decided for the use case 1 - classify the command,
        or 2 - get the car measurement.
        """
        
        messages = state["messages"]

        if '1.' in messages[-1].content:
            return "1."
        elif '2.' in messages[-1].content:
            return "2."
        else:
            raise ValueError("The 'decide_branch_model' should return only '1.' or '2.'")

    
    @staticmethod
    def print_stream(stream):
        """# Helper function for formatting the stream nicely

        Args:
            stream (_type_): _description_
        """
        for s in stream:
            # When the tool is not executed, the previous message is printed twice.
            # Here we avoid duplicates.
            prev_prev_msg = None
            if len(s["messages"]) > 1:
                prev_prev_msg = s["messages"][-2].content
            if len(s["messages"]) > 15:
                True
            if not s["messages"][-1].content == prev_prev_msg:
                message = s["messages"][-1]
                if isinstance(message, tuple):
                    print(message)
                else:
                    message.pretty_print()
                    
    
