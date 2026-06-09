# Dockerfile for PX4 & ROS2 Swarm Simulation
FROM osrf/ros:humble-desktop-full

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install core dependencies and VNC/noVNC tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    gnupg2 \
    lsb-release \
    sudo \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    xfce4 \
    xfce4-terminal \
    dbus-x11 \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    openjdk-17-jre-headless \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Add Gazebo Garden repository and install Gazebo
RUN curl https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends \
    gz-garden \
    libgz-transport12-dev \
    libgz-cmake3-dev \
    && rm -rf /var/lib/apt/lists/*

ENV GZ_VERSION=garden

# Create non-root developer user
RUN groupadd -g 1000 developer && \
    useradd -u 1000 -g developer -d /home/developer -m -s /bin/bash developer && \
    echo "developer ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER developer
WORKDIR /home/developer

# Install Python packages required for PX4 SITL
RUN pip3 install --no-cache-dir \
    kconfiglib \
    jinja2 \
    pyyaml \
    jsonschema \
    symforce \
    pyros-genmsg \
    numpy \
    future \
    empy==3.3.4

RUN which gz && gz sim --version && pkg-config --list-all | grep gz

# Clone and build Micro-XRCE-DDS-Agent
RUN git clone -b v2.4.3 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git && \
    cd Micro-XRCE-DDS-Agent && \
    mkdir build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    sudo make install && \
    sudo ldconfig && \
    cd ../.. && rm -rf Micro-XRCE-DDS-Agent


ENV CMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/cmake/gz-transport12:/usr/share/cmake/gz-cmake3

# Clone PX4 Autopilot (v1.14.2) and pre-compile the SITL target
RUN git clone --recursive --depth 1 --branch v1.14.2 https://github.com/PX4/PX4-Autopilot.git && \
    cd PX4-Autopilot && \
    DONT_RUN=1 make px4_sitl

# Setup ROS 2 workspace structure
RUN mkdir -p /home/developer/ros2_ws/src

# Clone the correct px4_msgs package to the workspace
RUN git clone -b release/1.14 https://github.com/PX4/px4_msgs.git /home/developer/ros2_ws/src/px4_msgs

# Build the base workspace (only px4_msgs initially)
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && cd /home/developer/ros2_ws && colcon build"

# Configure environment variables for noVNC, Gazebo, and ROS2
ENV DISPLAY=:1
ENV RESOLUTION=1280x800
ENV AMENT_PREFIX_PATH=/home/developer/ros2_ws/install/px4_msgs:/opt/ros/humble
ENV CMAKE_PREFIX_PATH=/home/developer/ros2_ws/install/px4_msgs:/opt/ros/humble
ENV COLCON_PREFIX_PATH=/home/developer/ros2_ws/install/px4_msgs
ENV LD_LIBRARY_PATH=/home/developer/ros2_ws/install/px4_msgs/lib:/opt/ros/humble/lib
ENV PATH=/home/developer/ros2_ws/install/px4_msgs/bin:/opt/ros/humble/bin:$PATH
ENV PYTHONPATH=/home/developer/ros2_ws/install/px4_msgs/local/lib/python3.10/dist-packages:/opt/ros/humble/local/lib/python3.10/dist-packages:$PYTHONPATH
ENV ROS_DISTRO=humble
ENV ROS_VERSION=2

# Copy the entrypoint script
COPY --chown=developer:developer entrypoint.sh /home/developer/entrypoint.sh
RUN chmod +x /home/developer/entrypoint.sh

# Expose noVNC port (8080) and Micro-XRCE-DDS Agent UDP port (15555)
EXPOSE 8080 15555/udp

ENTRYPOINT ["/home/developer/entrypoint.sh"]
