from pathlib import Path

from setuptools import setup

# requirements
requirements_path = Path("requirements.txt")
if requirements_path.exists():
    with open("requirements.txt") as f:
        required = f.read().splitlines()
else:
    required = []

# read readme
current_dir = Path(__file__).parent
long_description = (current_dir / "README.md").read_text()

setup(
    name='nanobind-stubgen',
    version='0.1.1',
    packages=['nanobind_stubgen'],
    url='https://github.com/cansik/nanobind-stubgen',
    license='MIT license',
    author='Florian Bruggisser',
    author_email='github@broox.ch',
    description='Generate python stub files for code completion in IDEs for nanobind modules.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=required,
    entry_points={
        'console_scripts': [
            'nanobind-stubgen = nanobind_stubgen.__main__:main',
        ],
    },
)
