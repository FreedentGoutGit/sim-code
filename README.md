# PX4 + ROS2 Swarm Simulation Environment

A containerized, self-contained development and testing environment for multi-vehicle drone swarms. It bridges **PX4 SITL** and **ROS2 Humble** using **Micro XRCE-DDS** as the middleware. It also provides a graphical desktop environment in your browser using **noVNC**, allowing you to see Gazebo and visualization tools without manual host display setup.

---

## Architecture Overview

```
                   +-------------------------------------------------+
                   |                Docker Container                 |
                   |                                                 |
                   | +---------------------------------------------+ |
                   | |               Xvfb (Display :1)             | |
                   | |                       ^                     | |
+---------------+  | |                       |                     | |
| Browser (Host)|  | |  +--------------------+------------------+  | |
|  noVNC Client |<=====|  noVNC (8080) -> x11vnc -> XFCE Desktop|  | |
+---------------+  | |                                          |  | |
                   | |   +------------------------------------+ |  | |
                   | |   |         Gazebo Sim (GUI)           | |  | |
                   | |   +------------------------------------+ |  | |
                   | +---------------------------------------------+ |
                   |                         ^                       |
                   |                         | (UDP Ports)           |
                   |         +---------------+---------------+       |
                   |         |               |               |       |
                   |     [Drone 1]       [Drone 2]       [Drone 3]   |
                   |      (px4_1)         (px4_2)         (px4_3)    |
                   |         |               |               |       |
                   |         +---------------+---------------+       |
                   |                         | (uORB)                |
                   |                         v                       |
                   |             +-----------------------+           |
                   |             |  Micro XRCE-DDS Agent |           |
                   |             +-----------------------+           |
                   |                         |                       |
                   |                         v (ROS2 DDS Topics)     |
                   |             +-----------------------+           |
                   |             |  ROS2 Swarm Controller|           |
                   |             +-----------------------+           |
                   +-------------------------------------------------+
```

- **PX4 Autopilot SITL:** Runs 3 separate instances of the PX4 flight controller (version 1.14.2). Each instance handles sensor processing, motor mixing, and flight control.
- **Gazebo Sim (Garden):** Simulates the physical world, quadcopter models (x500), and sensor readings (IMU, GPS, lidar).
- **Micro XRCE-DDS Agent:** Bridges uORB messages from the drones into native ROS 2 topics under corresponding namespaces (`/px4_1/...`, `/px4_2/...`, `/px4_3/...`).
- **noVNC & VNC Server:** Streams X11 window output via websockets to any browser on your host machine.
- **ROS2 Swarm Controller:** A Python-based node running inside the ROS2 environment, issuing offboard trajectory commands to guide the drones in a synchronized formation.

---

## Prerequisites

1. **Docker Desktop** installed on your Windows machine with the **WSL2 backend** enabled.
2. At least **4 CPUs** and **8 GB of RAM** allocated to Docker (configured in Docker Desktop settings) to support the multi-vehicle Gazebo simulation.

---

## Getting Started

### 1. Launch the Simulation Environment

Navigate to the project root directory in your terminal (PowerShell, Command Prompt, or WSL) and run:

```bash
docker-compose up --build -d
```

This will:
- Build the custom simulation Docker image (pre-compiling the PX4 binaries).
- Mount your host package (`ros2_ws/src/swarm_control`) into the container.
- Spin up Xvfb, XFCE4, noVNC, the Micro XRCE-DDS Agent, and 3 PX4 SITL drone instances inside Gazebo.

### 2. View the Simulation GUI

Once the container is running:
1. Open your browser and navigate to: **[http://localhost:8080/vnc.html](http://localhost:8080/vnc.html)**.
2. Click **Connect** (no password is required).
3. You will see an Ubuntu XFCE desktop environment. After Gazebo loads (usually takes 15–20 seconds on first run), **3 x500 drones** will appear spawned in a line at coordinates:
   - **Drone 1:** (0, 0, 0)
   - **Drone 2:** (0, 2, 0)
   - **Drone 3:** (0, 4, 0)

### 3. Run the Swarm Controller Node

To command the drones to takeoff and execute their formation, you need to launch the ROS2 swarm controller:

1. Open a terminal on your host machine.
2. Run a shell inside the running container:
   ```bash
   docker exec -it px4_ros2_sim bash
   ```
3. Source the ROS 2 workspace:
   ```bash
   source /home/developer/ros2_ws/install/setup.bash
   ```
4. Run the swarm controller:
   ```bash
   ros2 run swarm_control swarm_controller
   ```

### 4. Watch the Swarm Behaviors

Watch the Gazebo simulator window in your browser (noVNC tab). You will see the following flight mission occur:
1. **Takeoff:** Drones arm, switch to Offboard mode, and takeoff to hover at **2.5m** altitude.
2. **V-Formation:** Drones transition into a forward-pointing triangle formation:
   - **Drone 1 (Lead):** moves to (5, 2) relative to spawn at 3m altitude.
   - **Drone 2 (Left Wing):** moves to (3, 0) relative to spawn at 3m altitude.
   - **Drone 3 (Right Wing):** moves to (3, 4) relative to spawn at 3m altitude.
3. **Return to Base:** Drones fly back to their original hover positions above their spawns.
4. **Landing:** Drones trigger autonomous landing, descend slowly, touch down, and disarm.

---

## Development & Customization

### Modifying Swarm Behaviors

The source code for the swarm controller is located on your Windows host at:
`./ros2_ws/src/swarm_control/swarm_control/swarm_controller.py`

You can edit this file directly on Windows using VS Code or any text editor. Because this directory is mapped directly to the container, your changes are immediately visible inside Docker.

After modifying the script, rebuild and run it from the container shell:
```bash
# In the container terminal:
cd /home/developer/ros2_ws
colcon build --symlink-install
source install/setup.bash
ros2 run swarm_control swarm_controller
```

### Accessing Other Tools inside noVNC

Inside the noVNC desktop, you can:
- Open a terminal application (e.g. `xfce4-terminal`) to inspect active ROS 2 topics:
  ```bash
  ros2 topic list
  ros2 topic echo /px4_1/fmu/out/vehicle_odometry
  ```
- Run **rqt_graph** to visualize the node connectivity:
  ```bash
  rqt_graph
  ```

---

## Troubleshooting

### High CPU usage / Stuttering in Simulation
Simulating physics and 3D graphics for multiple drones is very CPU intensive. If the simulation is lagging:
- Open Gazebo, go to the top bar menu, select **View**, and uncheck **Grid** and other rendering details if necessary.
- In the `docker-compose.yml` file, ensure `shm_size` is set to `2gb` (this is already set).
- If the simulation time factor is very low (< 0.5), consider reducing the number of drones to 2 or running Docker with higher CPU allocations.

### Drones do not respond to commands
If the drones arm but refuse to move:
- Verify that the `MicroXRCEAgent` is running inside the container:
  ```bash
  ps aux | grep MicroXRCEAgent
  ```
- Check if ROS2 is receiving telemetry from the agent:
  ```bash
  ros2 topic list
  ```
  You should see topics like `/px4_1/fmu/out/vehicle_status`. If you do not see these topics, check the startup logs in `/tmp/px4_1.log` inside the container for DDS connection errors.
