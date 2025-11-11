# Curioso

## Overview

Curioso is a python api, CLI, for detect os information as json format:

### How to Install

```shell
$ uv add git+https://github.com/geopozo/curioso
# or
$ pip install git+https://github.com/geopozo/curioso
```

## Usage

```shell
$ curioso
```

## Python API

```python
import curioso

report = curioso.probe()
print(report)
```

## License

This project is licensed under the terms of the MIT license.
