import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter, ParameterValue
from rcl_interfaces.srv import SetParameters, GetParameters, ListParameters
from rcl_interfaces.msg import SetParametersResult, ParameterType
from std_msgs.msg import String
from functools import partial
from rclpy.callback_groups import ReentrantCallbackGroup, MutuallyExclusiveCallbackGroup
import time
import json
from pathlib import Path
from functools import partial
from adore_ros2_msgs.msg import PassengerRequest
from adore_ros2_msgs.msg import GoalPoint
import std_msgs.msg
from adore_ros2_msgs.msg import MissionCommand


class CommandDisseminationNode(Node):
    """
    This node subscribes to PassengerRequest messages, handles specific commands
    with dedicated logic, and republishes all other commands to a new topic.
    """
    def __init__(self):
        super().__init__('command_dissemination_node')

        # callback groups needed to for parameter getting service
        self.service_cb_group = ReentrantCallbackGroup()
        #self.pubsub_cb_group  = MutuallyExclusiveCallbackGroup()

        # Publisher for commands that are not handled by a specific case
        self.republisher = self.create_publisher(
            PassengerRequest,
            'passenger_request',
            10)

        # Publisher for commands that are not handled by a specific case
        self.goal_publisher = self.create_publisher(
            GoalPoint,
            'mission/goal_request',
            10)
        self.emergency_publisher = self.create_publisher(
            std_msgs.msg.Bool,
            'emergency_stop_request',
            10)
        self.back_to_start_publisher = self.create_publisher(
            std_msgs.msg.Bool,
            'mission/drive_back_to_start',
            10)
        
        # Subscriber to the incoming passenger requests
        self.subscription = self.create_subscription(
            PassengerRequest,
            'fm/passenger_request',
            self.command_callback,
            10)
        self.feedback_subscription_emergency_stop = self.create_subscription(
            std_msgs.msg.String,
            'emergency_stop_started',
            self.emergency_stop_feedback_callback,
            10)
        self.subscription  # prevent unused variable warning
        
        self._next_command_id = 1
        self.mission_command_publisher = self.create_publisher(
            MissionCommand,
              'mission_command',   
            10
        )
        self.decision_maker_node_name = "decision_maker"
        self.decision_maker_node_param_list_client = self.create_client(
            ListParameters,
            f'{self.decision_maker_node_name}/list_parameters',
            callback_group=self.service_cb_group
        )

        self._startup_inflight = False
        self._startup_param_names = []

        self.decision_maker_node_param_setter_client = self.create_client(
            SetParameters, f'{self.decision_maker_node_name}/set_parameters',
            callback_group=self.service_cb_group)
        self.decision_maker_node_param_getter_client = self.create_client(
            GetParameters, f'{self.decision_maker_node_name}/get_parameters',
            callback_group=self.service_cb_group)
        self.get_logger().info(f"Created getter client for service: {self.decision_maker_node_param_getter_client.srv_name}")
        self.available_decision_maker_parameters = {}
        self.startup_timer = self.create_timer(1.0, self.startup_parameter_discovery)

        self.std_factor = 1.3 
        self.declare_parameter("location_table_path", "")
        self.declare_parameter("default_goal_x", 0.0)
        self.declare_parameter("default_goal_y", 0.0)

        self.location_table_path = (
            self.get_parameter("location_table_path")
            .get_parameter_value()
            .string_value
        )

        self.default_goal = (
            self.get_parameter("default_goal_x").get_parameter_value().double_value,
            self.get_parameter("default_goal_y").get_parameter_value().double_value,
        )

        self.location_table = self.load_location_table(self.location_table_path)
        self.get_logger().info("Command Dissemination Node has started successfully.")


    def load_location_table(self, path: str) -> dict[str, tuple[float, float]]:
        if not path:
            self.get_logger().warn("No location_table_path set. Named goals will use default goal.")
            return {}

        try:
            file_path = Path(path)

            with file_path.open("r") as f:
                
                raw = json.load(f)

            table = {}
            for name, value in raw.items():
                key = str(name).lower().strip()

                if isinstance(value, dict):
                    table[key] = (float(value["x"]), float(value["y"]))
                else:
                    table[key] = (float(value[0]), float(value[1]))

            self.get_logger().info(f"Loaded {len(table)} named goal locations.")
            return table

        except Exception as e:
            self.get_logger().error(f"Failed to load location table '{path}': {e}")
            return {}


    def resolve_named_goal(self, name: str) -> tuple[float, float]:
        key = name.lower().strip()

        if key in self.location_table:
            return self.location_table[key]

        self.get_logger().warn(
            f"Unknown destination '{name}'. Using default goal {self.default_goal}."
        )
        return self.default_goal


    def get_factor_or_default(self, numerical_detail) -> float:
        if numerical_detail and len(numerical_detail) >= 1:
            return float(numerical_detail[0])
        return self.std_factor




    def command_callback(self, msg):
        
        name = [k for k, v in PassengerRequest.__dict__.items() if v == msg.type and not k.startswith('_')][0]
        self.get_logger().info("Received PassengerRequest with type: " + name + " (" + str(msg.type) + ")")
        self.get_logger().info(f"Numerical detail: {msg.numerical_detail}, Text detail: '{msg.text_detail}'")
        match msg.type:

            case PassengerRequest.SET_NEW_GOAL_POINT:
                self.handle_new_goal(msg.numerical_detail, msg.text_detail)
            # case PassengerRequest.DRIVE_MORE_SPORTILY:
            #     self.handle_driving_style("sportily", self.get_factor_or_default(msg.numerical_detail))

            # case PassengerRequest.DRIVE_MORE_COMFORTABLY:
            #     self.handle_driving_style("comfortably", self.get_factor_or_default(msg.numerical_detail))

            # case PassengerRequest.INCREASE_VELOCITY:
            #     self.handle_driving_style("velocity_up", self.get_factor_or_default(msg.numerical_detail))

            # case PassengerRequest.DECREASE_VELOCITY:
            #     self.handle_driving_style("velocity_down", self.get_factor_or_default(msg.numerical_detail))

            case PassengerRequest.EXECUTE_EMERGENCY_STOP:
                self.get_logger().info("Forwarding emergency stop as PassengerRequest")
                self.republisher.publish(msg)
            
            case PassengerRequest.EXECUTE_LANE_FOLLOWING:
                self.get_logger().info("perform lane following")

            case PassengerRequest.EXECUTE_LANE_CHANGE_LEFT:
                self.publish_mission_command(MissionCommand.CHANGE_LANE_LEFT)
            case PassengerRequest.EXECUTE_LANE_CHANGE_RIGHT:
                self.publish_mission_command(MissionCommand.CHANGE_LANE_RIGHT)
            case PassengerRequest.STOP_AND_LET_SB_BOARD:
                self.get_logger().info("stop and let sb board")

            case PassengerRequest.STOP_AND_LET_SB_EXIT:
                self.get_logger().info("stop and let sb exit (not yet implemented)")

            case PassengerRequest.STOP_AND_PARK:
                #self.get_logger().info("stop and park (not yet implemented)")
                self.publish_mission_command(MissionCommand.STOP_AND_PARK)

            case PassengerRequest.STAY_BEHIND_THE_VEHICLE_AHEAD:
                #self.handle_driving_style("no_overtake")
                self.get_logger().info("stay behind the vehicle ahead.")

            case PassengerRequest.TURN_RIGHT:
                self.get_logger().info("turn right")

            case PassengerRequest.TURN_LEFT:
                self.get_logger().info("turn left")

            case PassengerRequest.PERFORM_U_TURN:
                self.get_logger().info("perform u turn (not yet implemented)")

            case PassengerRequest.LEAVE_ROUNDABOUT_AT_EXIT_X:
                self.get_logger().info("leave roundabout at exit x (not yet implemented)")

            case PassengerRequest.CROSS_JUNCTION_STRAIGHT:
                self.get_logger().info("cross junction straight")

            case PassengerRequest.DRIVE_BACK_TO_START_POINT:
                self.handle_back_to_start()
                
            # case PassengerRequest.INCREASE_ACCELERATION_BOUNDS_LONGITUDINAL:
            #     self.get_logger().info("increase acceleration bounds longitudinal (not yet implemented)")
    
            # case PassengerRequest.DECREASE_ACCELERATION_BOUNDS_LONGITUDINAL:
            #     self.get_logger().info("decrease acceleration bounds longitudinal (not yet implemented)")

            # case PassengerRequest.INCREASE_ACCELERATION_BOUNDS_LATERAL:
            #     self.get_logger().info("increase acceleration bounds lateral (not yet implemented)")

            # case PassengerRequest.DECREASE_ACCELERATION_BOUNDS_LATERAL:
            #     self.get_logger().info("decrease acceleration bounds lateral (not yet implemented)")

            case PassengerRequest.RESUME_RIDE:
                self.get_logger().info("Forwarding resume ride as PassengerRequest")
                self.republisher.publish(msg)
            # case PassengerRequest.KEEP_MORE_DISTANCE:
            #     self.handle_driving_style("keep_more_distance")
            #     #self.get_logger().info("set parameters for distance keeping")

            case PassengerRequest.DRIVE_MORE_SPORTILY | \
                PassengerRequest.DRIVE_MORE_COMFORTABLY | \
                PassengerRequest.INCREASE_VELOCITY | \
                PassengerRequest.DECREASE_VELOCITY | \
                PassengerRequest.KEEP_MORE_DISTANCE | \
                PassengerRequest.INCREASE_ACCELERATION_BOUNDS_LONGITUDINAL | \
                PassengerRequest.DECREASE_ACCELERATION_BOUNDS_LONGITUDINAL | \
                PassengerRequest.INCREASE_ACCELERATION_BOUNDS_LATERAL | \
                PassengerRequest.DECREASE_ACCELERATION_BOUNDS_LATERAL:
                self.republisher.publish(msg)
            case _:
                self.get_logger().warn("command " + str(msg.type) + " not yet implemented")   
                #raise NotImplementedError("command " + str(msg.type) + " not yet implemented")


    def get_decision_maker_parameters_async(self, param_names: list[str]):
        if not self.decision_maker_node_param_getter_client.service_is_ready():
            self.get_logger().warn("GetParameters service not ready.")
            return None

        req = GetParameters.Request()

        req.names = param_names
        return self.decision_maker_node_param_getter_client.call_async(req)


    def set_decision_maker_parameters(self, params_dict: dict):
        
        params_to_set = [Parameter(name=key, value=value) for key, value in params_dict.items()]
        
        if not self.decision_maker_node_param_setter_client.service_is_ready():
            self.get_logger().error(
                "Service decision_maker_node_param_setter_client is not available. "
                "Cannot send parameter request."
            )
            return False

        request = SetParameters.Request()
        request.parameters = [p.to_parameter_msg() for p in params_to_set]

        on_response_with_context = partial(self.on_set_decision_maker_parameters_response, params_req=params_to_set)
        future = self.decision_maker_node_param_setter_client.call_async(request)
        future.add_done_callback(on_response_with_context)
        self.get_logger().info(f"Sent async request to set {len(params_to_set)} parameters.")

    def on_set_decision_maker_parameters_response(self, future, params_req: list[Parameter]):
      
        try:
            response = future.result()
            if response:
                for i, result in enumerate(response.results):
                    param_name = params_req[i].name
                    if result.successful:
                        self.get_logger().info(f"Successfully set parameter '{param_name}'")
                    else:
                        self.get_logger().error(
                            f"Failed to set parameter '{param_name}': {result.reason}"
                        )
            else:
                 self.get_logger().error(f'Service call failed with no response: {future.exception()}')

        except Exception as e:
            self.get_logger().error(f'Service call failed with exception: {e}')

    def multiply_decision_maker_parameters(self, param_factor_dict: dict):
        params_to_retrieve = [k for k in param_factor_dict.keys()
                            if k in self.available_decision_maker_parameters]
        print(f"Attempting to multiply parameters with factors: {param_factor_dict}")
        print(f"Parameters available for multiplication: {params_to_retrieve}")
        planner_settings_available = (
            "planner_settings_keys" in self.available_decision_maker_parameters and
            "planner_settings_values" in self.available_decision_maker_parameters
        )
        if planner_settings_available:
            params_to_retrieve += ["planner_settings_keys", "planner_settings_values"]

        if not params_to_retrieve:
            self.get_logger().warn("No matching parameters available to update.")
            return

        fut = self.get_decision_maker_parameters_async(params_to_retrieve)
        if fut is None:
            return
        

        print(f"fut is {fut}")

        fut.add_done_callback(partial(
            self._on_multiply_params_received,
            param_names=params_to_retrieve,
            param_factor_dict=param_factor_dict
        ))


    def _on_multiply_params_received(self, future, param_names, param_factor_dict):
        try:
            resp = future.result()
            retrieved = {
                n: self.get_python_value(v)
                for n, v in zip(param_names, resp.values)
            }
        except Exception as e:
            self.get_logger().error(f"GetParameters (multiply) failed: {e}")
            return

        updated_params = {}

        for key, value in retrieved.items():
            if value is None:
                continue

            if key == "planner_settings_values" and "planner_settings_keys" in retrieved:
                planner_keys = retrieved["planner_settings_keys"]
                planner_values = list(value)
                for i, planner_key in enumerate(planner_keys):
                    if planner_key in param_factor_dict:
                        print(f"Multiplying planner parameter '{planner_key}' value {planner_values[i]} by factor {param_factor_dict[planner_key]}")
                        planner_values[i] *= param_factor_dict[planner_key]
                updated_params[key] = planner_values

            elif key == "planner_settings_keys":
                updated_params[key] = value

            elif key in param_factor_dict:
                print(f"Multiplying parameter '{key}' value {value} by factor {param_factor_dict[key]}")
                updated_params[key] = value * param_factor_dict[key]

        if updated_params:
            self.set_decision_maker_parameters(updated_params)




        #updated_params = {
        #    key: value * param_factor_dict[key]
        #    for key, value in retrieved_params.items()
        #    if value is not None 
        #}
        #self.set_decision_maker_parameters(updated_params)
    """
    functions to handle specific commands
    handle emergency stop
    handle new goal
    handle driving style
    handle lane change
    handle stop and park
    handle info request
    ...
    """

    def publish_mission_command(self, command: int, enable: bool = True,
                            arg_int: int = 0, arg_float: float = 0.0):
        msg = MissionCommand()
        msg.command_id = self._next_command_id
        self._next_command_id += 1
        msg.command = command
        msg.enable = enable
        msg.arg_int = arg_int
        msg.arg_float = arg_float
        self.mission_command_publisher.publish(msg)
        self.get_logger().info(
            f"Published MissionCommand id={msg.command_id}, command={msg.command}, "
            f"enable={msg.enable}, arg_int={msg.arg_int}, arg_float={msg.arg_float}"
    )
    def emergency_stop_feedback_callback(self, msg):
        if msg.data:
            self.get_logger().info("Emergency stop has been started by decision_maker.")
        else:
            self.get_logger().info("Emergency stop has been cleared by decision_maker.")
        #emergency_msg = std_msgs.msg.Bool()
        #emergency_msg.data = False
        #self.emergency_publisher.publish(emergency_msg)
    
    def handle_back_to_start(self):
        self.get_logger().info("Handling drive back to start point command")
        back_to_start_msg = std_msgs.msg.Bool()
        back_to_start_msg.data = True
        self.back_to_start_publisher.publish(back_to_start_msg)

    def handle_emergency_stop(self):
        self.get_logger().info("Performing emergency stop")
        emergency_msg = std_msgs.msg.Bool()
        emergency_msg.data = True
        self.emergency_publisher.publish(emergency_msg)

    def handle_new_goal(self, numerical_detail, text_detail):
        if numerical_detail and len(numerical_detail) >= 2:
            x = float(numerical_detail[0])
            y = float(numerical_detail[1])
        else:
            x, y = self.resolve_named_goal(text_detail)

        goal_point = GoalPoint()
        goal_point.x_position = x
        goal_point.y_position = y
        self.goal_publisher.publish(goal_point)

        self.get_logger().info(f"Published goal point x={x}, y={y}")
        
    def handle_driving_style(self, detail, factor: float | None = None):
        if factor is None:
            factor = self.std_factor
        
        match detail:

            case "sportily":
                param_factor_dict = {
                    "comfort.max_acceleration": factor,
                    "comfort.min_acceleration": factor,
                    "comfort.desired_acceleration": factor,
                    "comfort.desired_deceleration": factor,
                    "comfort.max_lateral_acceleration": factor
                }
                self.multiply_decision_maker_parameters(param_factor_dict)

            case "comfortably":
                param_factor_dict = {
                    "comfort.max_acceleration": 1.0/factor,
                    "comfort.min_acceleration": 1.0/factor,
                    "comfort.desired_acceleration": 1.0/factor,
                    "comfort.desired_deceleration": 1.0/factor,
                    "comfort.max_lateral_acceleration": 1.0/factor
                }
                self.multiply_decision_maker_parameters(param_factor_dict)
            
            case "velocity_down":
                param_factor_dict = {
                    "comfort.max_speed": 1.0/factor,
                }
                self.multiply_decision_maker_parameters(param_factor_dict)

            case "velocity_up":
                param_factor_dict = {
                    "comfort.max_speed": factor,
                }
                self.multiply_decision_maker_parameters(param_factor_dict)
            case "keep_more_distance":

                param_factor_dict = {
                    "comfort.headway_scale": factor,
                }
                self.multiply_decision_maker_parameters(param_factor_dict)
            case _:
                raise ValueError(f"Invalid driving style detail received: '{detail}'")


    def wait_for_decision_maker_ready(self, max_retries: int = 10) -> bool:

        for attempt in range(max_retries):
            self.get_logger().info(f"Checking decision_maker readiness, attempt {attempt + 1}/{max_retries}")

            # Check if basic services are available
            if not self.decision_maker_node_param_getter_client.wait_for_service(timeout_sec=2.0):
                self.get_logger().warn("GetParameters service not yet available")
                time.sleep(1.0)
                continue

            # Try to list parameters - if it works, node is likely ready
            param_names = self.list_all_decision_maker_parameters()
            if len(param_names) > 0:  # Node has declared some parameters
                self.get_logger().info(f"Decision maker ready with {len(param_names)} parameters")
                return True
            else:
                self.get_logger().warn("Decision maker online but no parameters declared yet")
                time.sleep(2.0)  # Wait longer for parameter declaration

        self.get_logger().error("Decision maker not ready after maximum retries")
        return False

    def list_all_decision_maker_parameters(self) -> list[str]:
        list_client = self.create_client(
            ListParameters,
            f'{self.decision_maker_node_name}/list_parameters',
            callback_group=self.service_cb_group
        )

        if not list_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().error("ListParameters service not available.")
            return []

        request = ListParameters.Request()
        future = list_client.call_async(request)

        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)

        if not future.done():
            self.get_logger().error("ListParameters service call timed out.")
            return []

        try:
            response = future.result()
            param_names = response.result.names
            self.get_logger().info(f"Found {len(param_names)} parameters in decision_maker")
            return param_names
        except Exception as e:
            self.get_logger().error(f'ListParameters service call failed: {e}')
            return []

    def get_all_decision_maker_parameters(self) -> dict:
        # First get the list of all parameters
        param_names = self.list_all_decision_maker_parameters()

        if not param_names:
            self.get_logger().warn("No parameters found to retrieve")
            return {}

        # Then get their values
        all_params = self.get_decision_maker_parameters(param_names)

        if all_params:
            self.get_logger().info(f"Successfully retrieved {len(all_params)} parameters:")
            for name, value in all_params.items():
                self.get_logger().info(f"  {name}: {value}")

        return all_params or {}

    def startup_parameter_discovery(self):
        if self._startup_inflight:
            return  # Avoid overlapping calls
        
        if not self.decision_maker_node_param_list_client.service_is_ready():
            self.decision_maker_node_param_list_client.wait_for_service(timeout_sec=0.0)
            self.get_logger().info("Waiting for decision_maker/list_parameters ...")
            return

        if not self.decision_maker_node_param_getter_client.service_is_ready():
            self.decision_maker_node_param_getter_client.wait_for_service(timeout_sec=0.0)
            self.get_logger().info("Waiting for decision_maker/get_parameters ...")
            return

        self._startup_inflight = True

        req = ListParameters.Request()
        fut = self.decision_maker_node_param_list_client.call_async(req)
        fut.add_done_callback(self._on_startup_list_parameters)
    def _on_startup_list_parameters(self, future):
        try:
            resp = future.result()
            names = list(resp.result.names)
        except Exception as e:
            self.get_logger().error(f"ListParameters failed: {e}")
            self._startup_inflight = False
            return

        if not names:
            self.get_logger().warn("decision_maker has no parameters yet; retrying...")
            self._startup_inflight = False
            return

        self._startup_param_names = names

        req = GetParameters.Request()
        req.names = names
        fut = self.decision_maker_node_param_getter_client.call_async(req)
        fut.add_done_callback(self._on_startup_get_parameters)


    def _on_startup_get_parameters(self, future):
        try:
            resp = future.result()
            self.available_decision_maker_parameters = {
                name: self.get_python_value(v)
                for name, v in zip(self._startup_param_names, resp.values)
            }
            self.get_logger().info(
                f"Parameter discovery complete: {len(self.available_decision_maker_parameters)} parameters found"
            )
        except Exception as e:
            self.get_logger().error(f"GetParameters (startup) failed: {e}")
            self.available_decision_maker_parameters = {}
        finally:
            self._startup_inflight = False
            # stop the timer once done
            if hasattr(self, "startup_timer"):
                self.startup_timer.cancel()
                self.destroy_timer(self.startup_timer)

    def get_python_value(self, param_value: ParameterValue):
        param_type = param_value.type

        if param_type == ParameterType.PARAMETER_NOT_SET:
            return None
        elif param_type == ParameterType.PARAMETER_BOOL:
            return param_value.bool_value
        elif param_type == ParameterType.PARAMETER_INTEGER:
            return param_value.integer_value
        elif param_type == ParameterType.PARAMETER_DOUBLE:
            return param_value.double_value
        elif param_type == ParameterType.PARAMETER_STRING:
            return param_value.string_value
        elif param_type == ParameterType.PARAMETER_BYTE_ARRAY:
            return param_value.byte_array_value
        elif param_type == ParameterType.PARAMETER_BOOL_ARRAY:
            return param_value.bool_array_value
        elif param_type == ParameterType.PARAMETER_INTEGER_ARRAY:
            return param_value.integer_array_value
        elif param_type == ParameterType.PARAMETER_DOUBLE_ARRAY:
            return param_value.double_array_value
        elif param_type == ParameterType.PARAMETER_STRING_ARRAY:
            return param_value.string_array_value
        else:
            self.get_logger().warn(f"Unknown parameter type: {param_type}")
            return None


def main(args=None):
    rclpy.init(args=args)
    command_disseminator = CommandDisseminationNode()
    try:
        rclpy.spin(command_disseminator)
    except KeyboardInterrupt:
        pass
    command_disseminator.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()






    



