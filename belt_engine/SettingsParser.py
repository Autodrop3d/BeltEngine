# Copyright (c) 2020 Autodrop3D and Aldo Hoeben / fieldOfView
# BeltEngine is released under the terms of the AGPLv3 or higher.

import os
import json
import configparser
import ast
import re
from collections import OrderedDict
from typing import Any, List, Dict, Callable, Match, Set, Union, Optional

from .SettingFunction import SettingFunction

import logging
logger = logging.getLogger("BeltEngine")

class SettingsParser():
    def __init__(self, config_files=[], commandline_settings=[]):
        self._definitions = OrderedDict()
        definitions_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "definitions")
        for entry in os.scandir(definitions_folder):
            if entry.path.endswith(".def.json") and entry.is_file():
                self._definitions[os.path.basename(entry.path)] = SettingsDefinitionFile(entry.path)

        # parse config file and command-line settings
        if config_files == None:
            config_files = [[]]
        self._data = OrderedDict()
        for path in config_files[0]:
            config_file_path = os.path.abspath(path)
            if not os.path.exists(config_file_path):
                logger.error("Specified config file not found: %s" % config_file_path)
                continue

            logger.debug("Reading settings from %s" % config_file_path)
            with open(config_file_path) as config_file_pointer:
                config_file_content = config_file_pointer.read()
            if "[values]" not in config_file_content:
                config_file_content = "[values]\n" + config_file_content

            config_parser = configparser.ConfigParser()
            config_parser.read_string(config_file_content)
            for key, value in OrderedDict(config_parser["values"]).items():
                self.setSettingValue(key, value)

        if commandline_settings:
            settings = [tuple(setting_str[0].split("=", 1)) for setting_str in commandline_settings]
            for key, value in settings:
                self.setSettingValue(key, value)

        SettingFunction.registerOperator("extruderValue", self._getValueInExtruder)
        SettingFunction.registerOperator("extruderValues", self._getValuesInAllExtruders)
        SettingFunction.registerOperator("resolveOrValue", self._getResolveOrValue)
        SettingFunction.registerOperator("defaultExtruderPosition", self._getDefaultExtruderPosition)

    def getDefinition(self, key):
        for definition_file in self._definitions:
            definition = self._definitions[definition_file].getSettingDefinition(key)
            if definition:
                return definition
        logger.warning("Trying to get unknown setting %s" % key)
        return None

    def evaluateLeafValues(self):
        # parse setting value formulas
        for definition_file in self._definitions:
            definitions = self._definitions[definition_file].getDefinitions()
            for key, definition in definitions.items():
                if "leaf" not in definition:
                    continue
                if key in self._data:
                    continue

                if "value" in definition:
                    self.setSettingValue(key, definition["value"])
                else:
                    self._data[key] = definition["default_value"]

    def getNonDefaultValues(self):
        return self._data

    def getSettingValue(self, key):
        if key in self._data:
            return self._data[key]
        else:
            definition = self.getDefinition(key)
            if definition:
                if "value" in definition:
                    self.setSettingValue(key, definition["value"])
                    if key in self._data:
                        return self._data[key]

                return definition["default_value"]
        return None

    def setSettingValue(self, key, value):
        definition = self.getDefinition(key)
        if not definition:
            return
        if str(definition["default_value"]) == value:
            if key in self._data:
                del(self._data[key])
        else:
            self._data[key] = SettingFunction(value)(self)

    # Gets the default extruder position of the currently active machine.
    def _getDefaultExtruderPosition(self) -> str:
        return "0"

    # Gets the given setting key from the given extruder position.
    def _getValueInExtruder(self, extruder_position: int, property_key: str) -> Any:
        return self.getSettingValue(property_key)

    # Gets all extruder values as a list for the given property.
    def _getValuesInAllExtruders(self, property_key: str) -> List[Any]:
        return [self.getSettingValue(property_key)]

    # Get the resolve value or value for a given key.
    def _getResolveOrValue(self, property_key: str) -> Any:
        return self.getSettingValue(property_key)


class SettingsDefinitionFile():
    def __init__(self, file_path):
        self._data = {}
        with open(file_path) as json_data:
            parsed_data = json.load(json_data)
            if "settings" in parsed_data:
                self._data = self._parseSettings(parsed_data["settings"])

    def getSettingDefinition(self, key):
        if key in self._data:
            return self._data[key]
        else:
            return None

    def getDefinitions(self):
        return self._data

    def _parseSettings(self, settings):
        settings_dict = OrderedDict()
        for key in settings:
            setting = settings[key]
            if setting["type"] != "category":
                settings_dict[key] = {
                    "default_value": setting["default_value"],
                    "type": setting["type"]
                }
                if "value" in setting:
                    settings_dict[key]["value"] = setting["value"]

            if "children" in setting:
                leaf_dict = self._parseSettings(setting["children"])
                for leaf_key in leaf_dict:
                    settings_dict[leaf_key] = leaf_dict[leaf_key]
            elif key in settings_dict:
                settings_dict[key]["leaf"] = True
        return settings_dict
