from io import FileIO
import toml

from pydantic import ValidationError
from pydantic_env import config_validation_errors
from .config_models import ConfigModel


def load_config_file(filepath: FileIO):
    try:
        return ConfigModel.parse_obj(toml.load(filepath))

    except ValidationError as exc:
        raise RuntimeError(
            config_validation_errors(errors=exc.errors(), filepath=filepath.name)
        )
