# Curioso

## Overview

Curioso is a python api, CLI, for detecting operating system information and
reporting in a JSON format.

### How to Install

```shell
uv add git+https://github.com/geopozo/curioso
# or
pip install git+https://github.com/geopozo/curioso
```

## Usage

```shell
uv run curioso
# or
python -m curioso
```

## Python API

```python
import curioso

report = curioso.probe()
print(report)
```

## License

This project is licensed under the terms of the MIT license.
