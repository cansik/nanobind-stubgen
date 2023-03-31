# nanobind-stubgen [![PyPI](https://img.shields.io/pypi/v/nanobind-stubgen)](https://pypi.org/project/nanobind-stubgen/)

Generate Python stub files (`pyi`) for code completion in IDEs for [nanobind](https://github.com/wjakob/nanobind) modules.

### Installation

```
pip install nanobind-stubgen
```

### Usage

Nanobind stubgen uses the `inspect` module to reverse engineer the module structure and detects nanobind types. The doc
string of the nanobind types contains the function signature, which will be used to create the stub files.

To create pyi files for a module, first install the module and call `nanobind-stubgen` with the module name as first argument. 
Here is an example on how to generate stubs for [nanogui](https://github.com/mitsuba-renderer/nanogui):

```bash
nanobind-stubgen nanogui
```

It is possible to change the output path (by default it is the current directory) by specifying the parameter `--out`. To
create the pyi files directly in the nanogui package directory, the following command can be used (note the
changing python version):

```bash
nanobind-stubgen nanogui --out venv/lib/python3.9/site-packages
```

### Limitations
- The stub generator does not use the nanobind project, but the actual compiled python module. This means, that the generator can only detect module and function information that has been writen into the `__doc__` string by nanobind.
- No imports in the pyi files are currently added
 
### Help

```bash
usage: nanobind-stubgen [-h] [--out OUT] module

Nanobind Stubs Generator

positional arguments:
  module      Module to create stubs (e.g. nanogui).

optional arguments:
  -h, --help  show this help message and exit
  --out OUT   Output path for the generated pyi files.
```

### About
MIT License