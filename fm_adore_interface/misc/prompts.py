classification_prompt =\
    """
    ### Instructions:
    
    You are a part of a speech-to-text system enabling users to give vocal commands to a car.
    The first stage of the system translates the vocal commands into text.
    And you are part of the second stage that classify the natural language commands into
    a list of car actions.
    
    {car_actions_l}
    
    You task is to classify the input text into car actions.
    Answer only tha car action, no additional text.
    
    ### Examples:
    
    Command: Ich möchte langsamer fahren.
    Action: 6. slow down
    
    Command: My friend is here. Stop next to the house to let him in.
    Action: 7. stop and let someone board
    
    Command: Du bist zu nah vom Auto vorne.
    Action: 20. keep more distance.
    
    Command: Ich habe meine Schlüsseln vergessen. Fahr zurück heim.
    Action: 16. drive back to start point
    
    ### Your turn
    
    Command: {command_txt} 
    Action: 
    """
 
    
car_actions_l =\
    """
    List of car actions:

    1. EXECUTE_EMERGENCY_STOP: Stop as soon and quickly as possible.
    2. EXECUTE_LANE_FOLLOWING: Continue on the same lane, without junctions.
    3. EXECUTE_LANE_CHANGE_LEFT: Go to the left lane.
    4. EXECUTE_LANE_CHANGE_RIGHT: Go to the right lane.
    5. INCREASE_VELOCITY: Drive faster.
    6. DECREASE_VELOCITY: Slow down.
    7. STOP_AND_LET_SB_BOARD: Stop the vehicle in order to let somebody board.
    8. STOP_AND_LET_SB_EXIT: Stop the vehicle in order to let somebody exit.
    9. STOP_AND_PARK: Stop and park the vehicle without letting passengers in or out.
    10. STAY_BEHIND_THE_VEHICLE_AHEAD: Do not overtake the vehicle ahead and stay in lane behind it.
    11. TURN_RIGHT: Turn to the right.
    12. PERFORM_U_TURN: Perform a u-turn at the next possibility.
    13. LEAVE_ROUNDABOUT_AT_EXIT_X: Exit the roundabout at the specified exit.
    14. CROSS_JUNCTION_STRAIGHT: Continue on the same road through the next junction.
    15. TURN_LEFT: Turn to the left.
    16. DRIVE_BACK_TO_START_POINT: Change the destination to the starting point.
    17. DRIVE_MORE_COMFORTABLY: Do not allow high acceleration values.
    18. DRIVE_MORE_SPORTILY: Allow higher acceleration values.
    19. RESUME_RIDE: Continue the ride.
    20. KEEP_MORE_DISTANCE: Keep more distance to other vehicles.
    21. SET_NEW_GOAL_POINT: Drive to new destination xyz.
    """
    
correction_prompt =\
    """
    ### Instructions:

    You are a part of speech-to-text system enabling users to give vocal commands to a car.
    The first stage of the system translates the vocal commands into text.
    And you are part of the second stage that classify the natural language commands into
    a list of car actions.
    
    The translation of the commands might contain spelling or grammatical mistakes due to the speech-to-text system.
    Correct the mistakes if you find some, otherwise, return the text of the command.
    Do not provide any explanations.
    
    ### Examples:
    
    Command: Turn right at the next intersection.
    Correction: Turn right at the next intersection.
    
    Command: Geh shneller, ich bin speit.
    Correction: Geh schneller, ich bin spät.
    
    Command: Nimm die nächste Strasse links.
    Correction: Nimm die nächste Straße links.
    
    Command: ch machte den AUto vorne folgeb.
    Correction: Ich möchte dem Auto vorne folgen.
    
    Command: Stopp hier, wir sind angekommen.
    Correction: Stopp hier, wir sind angekommen.
    
    
    ### Your turn:
    Command: {command_txt}
    Correction:
    """
    
classif_correct_prompt =\
    """
    ### Instructions:
    
    You are a part of a speech-to-text system enabling users to give vocal commands to a car.
    The first stage of the system translates the vocal commands into text.
    And you are part of the second stage that classify the natural language commands into
    a list of car actions.
    
    {car_actions_l}
    
    A previous LLM agent has classified these natural language commands into car actions,
    but they may contain mistakes.
    Your task is to correct these mistakes if they happen, 
    otherwise return the same answer as the previous LLM.
    Do not write any explanations or additional text.
    
    ### Examples:
    
    Command: Ich möchte langsamer fahren.
    Prediction:  6. DECREASE_VELOCITY
    Correction: 6. DECREASE_VELOCITY
    
    Command: Go on the left lane.
    Prediction:  4. EXECUTE_LANE_CHANGE_LEFT 
    Correction: 3. EXECUTE_LANE_CHANGE_LEFT 
    
    Command: Fahr zurück nach Hause, ich möchte mich einen Sandwich tun.
    Prediction:  21. SET_NEW_GOAL_POINT
    Correction: 16. DRIVE_BACK_TO_START_POINT
    
    Command: Ich muss hier aussteigen.
    Prediction: 16. DRIVE_BACK_TO_START_POINT
    Correction: 8. STOP_AND_LET_SB_EXIT
    
    Command: Continue straight at the crossing.
    Prediction: 14. CROSS_JUNCTION_STRAIGHT
    Correction: 14. CROSS_JUNCTION_STRAIGHT
    
    ### Your turn
    
    Command: {command_txt} 
    Prediction: {prediction_text}
    Correction: 
    """
    
car_prompt =\
    """
    You are an AI retrieving measurement from an autonomous car.
    The values of the measurements are stored in a csv file.
    Your role is to give back the values asked by the user.
    Answer only the values requested.
    
    The dataframe is:
    {df}
    User question: {question}
    """
    
decide_branch_prompt =\
    """
    You are part of an AI system in an autonomous car.
    The AI system has 2 use cases:
    1. classify a vocal command from a user to a list of car actions
    2. retrieve car measurements
    
    The list of car actions is:
    {car_action_l}
    
    And the car measurements are in this dataframe:
    {df}
    
    Your role is to decide which use case is relevant.
    Answer only '1.' or '2.' .
    If you are unsure, answer 1.
    
    The user question is:
    {question}
    """