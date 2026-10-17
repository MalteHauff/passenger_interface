from setuptools import find_packages, setup
import os
import glob



package_name = 'passenger_interface'




# Read requirements from requirements.txt
def read_requirements():
    requirements_file = 'requirements.pip3'
    if os.path.exists(requirements_file):
        with open(requirements_file, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []




setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'),
            glob.glob('launchfiles/*.py')),
        (os.path.join('share', package_name),
            glob.glob(package_name + '/locations.json')),
        (os.path.join('share', package_name, 'data'), glob.glob(package_name + '/data/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vboxuser',
    maintainer_email='vboxuser@todo.todo',
    description='TODO: Package description',
    license='EPL-2.0',
    #tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'speech_to_text = passenger_interface.speech_to_text_node:main',
            'text_to_command = passenger_interface.text_to_command_node:main',
            'command_dissemination = passenger_interface.command_dissemination_node:main',
            'simulation_node = passenger_interface.simulation_node:main', 
        ],
    },
)

