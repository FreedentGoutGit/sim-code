#!/usr/bin/env python3
"""
Swarm Controller for PX4 & ROS2
Controls a swarm of 3 drones (px4_1, px4_2, px4_3) in Gazebo SITL simulation.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy

# Import PX4 messages
from px4_msgs.msg import (
    OffboardControlMode,
    TrajectorySetpoint,
    VehicleCommand,
    VehicleStatus,
    VehicleOdometry
)

class SingleDroneController:
    """
    Helper class to manage communication and state for a single drone in the swarm.
    """
    def __init__(self, node: Node, namespace: str, drone_id: int):
        self.node = node
        self.namespace = namespace
        self.drone_id = drone_id
        
        # Telemetry state
        self.armed = False
        self.nav_state = 0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.pos_z = 0.0
        
        # Set up QoS profile to match PX4 uXRCE-DDS standard
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )
        
        # Publishers
        self.offboard_mode_pub = self.node.create_publisher(
            OffboardControlMode,
            f'/{self.namespace}/fmu/in/offboard_control_mode',
            qos_profile
        )
        self.trajectory_pub = self.node.create_publisher(
            TrajectorySetpoint,
            f'/{self.namespace}/fmu/in/trajectory_setpoint',
            qos_profile
        )
        self.command_pub = self.node.create_publisher(
            VehicleCommand,
            f'/{self.namespace}/fmu/in/vehicle_command',
            qos_profile
        )
        
        # Subscribers
        self.status_sub = self.node.create_subscription(
            VehicleStatus,
            f'/{self.namespace}/fmu/out/vehicle_status',
            self.status_callback,
            qos_profile
        )
        self.odometry_sub = self.node.create_subscription(
            VehicleOdometry,
            f'/{self.namespace}/fmu/out/vehicle_odometry',
            self.odometry_callback,
            qos_profile
        )

    def status_callback(self, msg: VehicleStatus):
        self.armed = (msg.arming_state == VehicleStatus.ARMING_STATE_ARMED)
        self.nav_state = msg.nav_state

    def odometry_callback(self, msg: VehicleOdometry):
        # Position is in NED (North, East, Down)
        self.pos_x = msg.position[0]
        self.pos_y = msg.position[1]
        self.pos_z = msg.position[2]

    def publish_offboard_heartbeat(self):
        """Publishes the 2Hz proof-of-life signal required by PX4 to remain in Offboard mode."""
        msg = OffboardControlMode()
        msg.timestamp = int(self.node.get_clock().now().nanoseconds / 1000)
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        self.offboard_mode_pub.publish(msg)

    def publish_trajectory_setpoint(self, x: float, y: float, z: float, yaw: float = 0.0):
        """Sends a target position (NED coordinate frame) to the autopilot."""
        msg = TrajectorySetpoint()
        msg.timestamp = int(self.node.get_clock().now().nanoseconds / 1000)
        msg.position = [x, y, z]
        msg.yaw = yaw
        self.trajectory_pub.publish(msg)

    def send_vehicle_command(self, command: int, param1: float = 0.0, param2: float = 0.0):
        """Helper to send MAVLink command to the autopilot."""
        msg = VehicleCommand()
        msg.timestamp = int(self.node.get_clock().now().nanoseconds / 1000)
        msg.command = command
        msg.param1 = param1
        msg.param2 = param2
        msg.target_system = self.drone_id + 1  # Map instance to target system ID
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        self.command_pub.publish(msg)

    def arm(self):
        self.node.get_logger().info(f"[{self.namespace}] Sending arm command...")
        self.send_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 1.0)

    def disarm(self):
        self.node.get_logger().info(f"[{self.namespace}] Sending disarm command...")
        self.send_vehicle_command(VehicleCommand.VEHICLE_CMD_COMPONENT_ARM_DISARM, 0.0)

    def set_offboard_mode(self):
        self.node.get_logger().info(f"[{self.namespace}] Requesting Offboard mode...")
        # Main mode: 1 (custom main mode enable), Sub mode: 6 (Offboard)
        self.send_vehicle_command(VehicleCommand.VEHICLE_CMD_DO_SET_MODE, 1.0, 6.0)

    def land(self):
        self.node.get_logger().info(f"[{self.namespace}] Requesting Land mode...")
        self.send_vehicle_command(VehicleCommand.VEHICLE_CMD_NAV_LAND)


class SwarmController(Node):
    """
    ROS2 Swarm Controller node that coordinates the behavior of multiple UAVs.
    """
    def __init__(self):
        super().__init__('swarm_controller')
        self.get_logger().info("Initializing Swarm Controller...")

        # Initialize the 3 drones
        self.drones = [
            SingleDroneController(self, 'px4_1', drone_id=1),
            SingleDroneController(self, 'px4_2', drone_id=2),
            SingleDroneController(self, 'px4_3', drone_id=3)
        ]

        # Timer to run controller loop at 10 Hz
        self.timer_period = 0.1  # seconds
        self.timer = self.create_timer(self.timer_period, self.control_loop)
        
        # State machine variables
        self.state_counter = 0
        self.state = "INIT"
        self.get_logger().info("Swarm controller state machine starting in state: INIT")

    def control_loop(self):
        # 1. Always publish heartbeat and current target setpoints to keep Offboard mode active
        self.publish_heartbeats()
        
        # 2. State Machine for Swarm coordination
        self.state_counter += 1
        
        if self.state == "INIT":
            # Wait for telemetry to stabilize, stream heartbeats
            # Takeoff after 3 seconds (30 ticks)
            self.send_all_targets(0.0, 0.0, -1.0) # Hover slightly off the ground
            if self.state_counter > 30:
                self.state = "ARM_AND_OFFBOARD"
                self.state_counter = 0
                self.get_logger().info("Switching state to: ARM_AND_OFFBOARD")

        elif self.state == "ARM_AND_OFFBOARD":
            # First set to offboard mode, then arm
            for drone in self.drones:
                drone.set_offboard_mode()
                drone.arm()
            
            # Transition to takeoff hovering after 3 seconds
            self.send_all_targets(0.0, 0.0, -2.5) # Hover at 2.5m
            if self.state_counter > 30:
                self.state = "TAKEOFF"
                self.state_counter = 0
                self.get_logger().info("Switching state to: TAKEOFF")

        elif self.state == "TAKEOFF":
            # Hover in place at 2.5m
            self.send_all_targets(0.0, 0.0, -2.5)
            
            # Wait 10 seconds to stabilize
            if self.state_counter > 100:
                self.state = "FORMATION"
                self.state_counter = 0
                self.get_logger().info("Switching state to: FORMATION (V-Shape)")

        elif self.state == "FORMATION":
            # Fly drones into a forward-facing V-formation:
            # - Drone 1 (Lead): Move 5m forward, up to 3m altitude -> [5.0, 2.0, -3.0] relative to spawn
            # - Drone 2 (Left): Move 3m forward, left -> [3.0, -2.0, -3.0] relative to spawn
            # - Drone 3 (Right): Move 3m forward, right -> [3.0, 0.0, -3.0] relative to spawn
            # (Calculated to form a triangle pointing North)
            self.drones[0].publish_trajectory_setpoint(5.0, 2.0, -3.0)
            self.drones[1].publish_trajectory_setpoint(3.0, -2.0, -3.0)
            self.drones[2].publish_trajectory_setpoint(3.0, 0.0, -3.0)
            
            # Maintain formation for 20 seconds (200 ticks)
            if self.state_counter > 200:
                self.state = "RETURN_TO_BASE"
                self.state_counter = 0
                self.get_logger().info("Switching state to: RETURN_TO_BASE")

        elif self.state == "RETURN_TO_BASE":
            # Move back to their respective takeoff hover points
            self.send_all_targets(0.0, 0.0, -2.5)
            
            # Stay there for 10 seconds
            if self.state_counter > 100:
                self.state = "LAND"
                self.state_counter = 0
                self.get_logger().info("Switching state to: LAND")

        elif self.state == "LAND":
            # Send Land command to all drones
            for drone in self.drones:
                drone.land()
                
            # Wait for them to touch down (20 seconds) before disarming
            if self.state_counter > 200:
                self.state = "DISARM"
                self.state_counter = 0
                self.get_logger().info("Switching state to: DISARM")

        elif self.state == "DISARM":
            for drone in self.drones:
                drone.disarm()
            self.state = "FINISHED"
            self.get_logger().info("Swarm flight mission completed successfully!")

        elif self.state == "FINISHED":
            # Do nothing
            pass

    def publish_heartbeats(self):
        for drone in self.drones:
            drone.publish_offboard_heartbeat()

    def send_all_targets(self, x: float, y: float, z: float):
        for drone in self.drones:
            drone.publish_trajectory_setpoint(x, y, z)


def main(args=None):
    rclpy.init(args=args)
    node = SwarmController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Swarm controller interrupted by user.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
