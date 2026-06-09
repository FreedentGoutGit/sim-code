from setuptools import setup

package_name = 'swarm_control'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='developer',
    maintainer_email='developer@todo.todo',
    description='ROS 2 Python node to control a swarm of PX4 UAVs via Micro XRCE-DDS',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'swarm_controller = swarm_control.swarm_controller:main'
        ],
    },
)
