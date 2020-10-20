# Copyright (c) 2020 Autodrop3D and Aldo Hoeben / fieldOfView
# BeltEngine is released under the terms of the AGPLv3 or higher.

import os
import re

import logging
logger = logging.getLogger("BeltEngine")

class GcodePostProcessor():
    def __init__(self,
                belt_wall_enable = False,
                belt_wall_flow = 100,
                belt_wall_speed = 30,
                wall_line_width_0 = 0.4
        ):

        self._belt_wall_enable = belt_wall_enable
        self._belt_wall_flow = belt_wall_flow / 100
        self._belt_wall_speed = belt_wall_speed * 60
        self._minimum_y = wall_line_width_0 * 0.6 #  0.5 would be non-tolerant

    def processGcodeFile(self, file_path):
        gcode_lines = self._openGcodeFile(file_path)
        gcode_lines = self.processGcode(gcode_lines)
        self._writeGcodeFile(file_path, gcode_lines)

    def _openGcodeFile(self, file_path):
        file_pointer = open(os.path.abspath(file_path), "r")
        gcode_lines = file_pointer.readlines()
        file_pointer.close()
        return gcode_lines

    def _writeGcodeFile(self, file_path, gcode_lines):
        file_pointer = open(os.path.abspath(file_path), "w")
        file_pointer.writelines(gcode_lines)
        file_pointer.close()

    def processGcode(self, gcode_lines):
        # adjust walls that touch the belt
        if self._belt_wall_enable:
            y = None
            last_y = None
            e = None
            last_e = None
            f = None

            speed_regex = re.compile(r" F\d*\.?\d*")
            extrude_regex = re.compile(r" E-?\d*\.?\d*")
            move_parameters_regex = re.compile(r"([YEF]-?\d*\.?\d+)")

            #for layer_number, layer in enumerate(gcode_list):
            #    if layer_number < 2 or layer_number > len(gcode_list) - 1:
            #        # gcode_list[0]: curaengine header
            #        # gcode_list[1]: start gcode
            #        # gcode_list[2] - gcode_list[n-1]: layers
            #        # gcode_list[n]: end gcode
            #        continue

            layer_number = -1
            for line_number, line in enumerate(gcode_lines):
                if line.startswith(";LAYER:"):
                    layer_number = int(line[7:])
                if layer_number < 1:
                    continue

                line_has_e = False
                line_has_axis = False

                gcode_command = line.split(' ', 1)[0]
                if gcode_command not in ["G0", "G1", "G92"]:
                    continue

                result = re.findall(move_parameters_regex, line)
                if not result:
                    continue

                for match in result:
                    parameter = match[:1]
                    value = float(match[1:])
                    if parameter == "Y":
                        y = value
                        line_has_axis = True
                    elif parameter == "E":
                        e = value
                        line_has_e = True
                    elif parameter == "F":
                        f = value
                    elif parameter in "XZ":
                        line_has_axis = True

                if gcode_command != "G92" and line_has_axis and line_has_e and f is not None and y is not None and y <= self._minimum_y and last_y is not None and last_y <= self._minimum_y:
                    if f > self._belt_wall_speed:
                        # Remove pre-existing move speed and add our own
                        line = re.sub(speed_regex, r"", line)

                    if self._belt_wall_flow != 1.0 and last_y is not None:
                        new_e = last_e + (e - last_e) * self._belt_wall_flow
                        line = re.sub(extrude_regex, " E%f" % new_e, line)
                        line = line.strip() + " ; Adjusted E for belt wall\nG92 E%f ; Reset E to pre-compensated value\n" % e

                    if f > self._belt_wall_speed:
                        g_type = int(line[1:2])
                        line = "G%d F%d ; Belt wall speed\n%s\nG%d F%d ; Restored speed\n" % (g_type, self._belt_wall_speed, line.strip(), g_type, f)

                    gcode_lines[line_number] = line

                last_y = y
                last_e = e

        return gcode_lines