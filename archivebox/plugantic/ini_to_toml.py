from typing import Any, List, Callable

import json
import ast
import inspect
import configparser

from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import to_jsonable_python

JSONValue = str | bool | int | None | List['JSONValue']

TOML_HEADER = "# Converted from INI to TOML format: https://toml.io/en/\n\n"

def load_ini_value(val: str) -> JSONValue:
    """Convert lax INI values into strict TOML-compliant (JSON) values"""
    if val.lower() in ('true', 'yes', '1'):
        return True
    if val.lower() in ('false', 'no', '0'):
        return False
    if val.isdigit():
        return int(val)

    try:
        return ast.literal_eval(val)
    except Exception:
        pass

    try:
        return json.loads(val)
    except Exception:
        pass
    
    return val


def convert(ini_str: str) -> str:
    """Convert a string of INI config into its TOML equivalent (warning: strips comments)"""

    config = configparser.ConfigParser()
    config.optionxform = str  # capitalize key names
    config.read_string(ini_str)

    # Initialize an empty dictionary to store the TOML representation
    toml_dict = {}

    # Iterate over each section in the INI configuration
    for section in config.sections():
        toml_dict[section] = {}

        # Iterate over each key-value pair in the section
        for key, value in config.items(section):
            parsed_value = load_ini_value(value)

            # Convert the parsed value to its TOML-compatible JSON representation
            toml_dict[section.upper()][key.upper()] = json.dumps(parsed_value)

    # Build the TOML string
    toml_str = TOML_HEADER
    for section, items in toml_dict.items():
        toml_str += f"[{section}]\n"
        for key, value in items.items():
            toml_str += f"{key} = {value}\n"
        toml_str += "\n"

    return toml_str.strip()



class JSONSchemaWithLambdas(GenerateJsonSchema):
    def encode_default(self, default: Any) -> Any:
        """Encode lambda functions in default values properly"""
        config = self._config
        if isinstance(default, Callable):
            return '{{lambda ' + inspect.getsource(default).split('=lambda ')[-1].strip()[:-1] + '}}'
        return to_jsonable_python(
           default,
           timedelta_mode=config.ser_json_timedelta,
           bytes_mode=config.ser_json_bytes,
           serialize_unknown=True
        )

    # for computed_field properties render them like this instead:
    # inspect.getsource(field.wrapped_property.fget).split('def ', 1)[-1].split('\n', 1)[-1].strip().strip('return '),

