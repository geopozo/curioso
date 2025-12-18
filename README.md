# Curioso

<h1
  align="center"
>
	  <img
        height="250"
        width="250"
        alt="curioso_small"
        src="https://raw.githubusercontent.com/geopozo/curioso/main/docs/media/logo.png">
</h1>

## Overview

Curioso is a python api, CLI, for detecting operating system information and
reporting in a JSON format.

### How to Install

```shell
uv add curioso
# or
pip install curioso
```

## Usage

```shell
uv run curioso
# or
python -m curioso
```

## Python API

```python
from curioso import ReportInfo

report = await ReportInfo.probe()
```

## License

This project is licensed under the terms of the MIT license.
