#!/bin/bash
set -e

echo "=== Starting Xvfb (Virtual Display :1) ==="
Xvfb :1 -screen 0 ${RESOLUTION}x24 &
sleep 2

echo "=== Starting XFCE Desktop ==="
export DISPLAY=:1
xfce4-session &
sleep 2

echo "=== Starting VNC Server ==="
x11vnc -display :1 -nopw -forever -shared -bg -rfbport 5900 &
sleep 2

echo "=== Starting noVNC Web GUI (Port 8080) ==="
/usr/share/novnc/utils/launch.sh --vnc localhost:5900 --listen 8080 &
sleep 2

echo "=== Building ROS 2 Workspace ==="
source /opt/ros/humble/setup.bash
cd /home/developer/ros2_ws
colcon build --symlink-install
source install/setup.bash

echo "=== Starting Micro XRCE-DDS Agent ==="
# Launch the agent on port 15555 (default client port for PX4 v1.14)
MicroXRCEAgent udp4 -p 15555 &
sleep 2

echo "=== Spawning Drone Swarm (3 Drones) ==="
cd /home/developer/PX4-Autopilot

# Drone 1 (Simulation Server)
# Automatically launches Gazebo GZ Server and client.
# Spawns at (0, 0)
echo "Launching Drone 1 (px4_1) at (0, 0)..."
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_UXRCE_DDS_NS=px4_1
./build/px4_sitl_default/bin/px4 -i 1 > /tmp/px4_1.log 2>&1 &

# Wait for Gazebo server to spin up fully before connecting clients
sleep 15

# Drone 2 (Standalone Client)
# Spawns at (0, 2)
echo "Launching Drone 2 (px4_2) at (0, 2)..."
export PX4_GZ_STANDALONE=1
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_GZ_MODEL_POSE="0,2"
export PX4_UXRCE_DDS_NS=px4_2
./build/px4_sitl_default/bin/px4 -i 2 > /tmp/px4_2.log 2>&1 &
sleep 2

# Drone 3 (Standalone Client)
# Spawns at (0, 4)
echo "Launching Drone 3 (px4_3) at (0, 4)..."
export PX4_GZ_STANDALONE=1
export PX4_SYS_AUTOSTART=4001
export PX4_SIM_MODEL=gz_x500
export PX4_GZ_MODEL_POSE="0,4"
export PX4_UXRCE_DDS_NS=px4_3
./build/px4_sitl_default/bin/px4 -i 3 > /tmp/px4_3.log 2>&1 &

echo "=== Drone Swarm Simulation Environment Ready! ==="
echo "Access noVNC Desktop at: http://localhost:8080/vnc.html"
echo "Keep-alive loop starting..."

# Monitor background processes and stream logs to docker logs
tail -f /tmp/px4_1.log &
tail -f /tmp/px4_2.log &
tail -f /tmp/px4_3.log &

# Keep container running
wait
