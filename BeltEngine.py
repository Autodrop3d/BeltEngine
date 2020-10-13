#!/usr/bin/env python3

# Copyright (c) 2020 Autodrop3D and Aldo Hoeben / fieldOfView
# BeltEngine is released under the terms of the AGPLv3 or higher.

import sys
import os
import argparse
from collections import OrderedDict
import configparser
import trimesh
import tempfile
import subprocess

import logging
logger = logging.getLogger("BeltEngine")
from colorlog import ColoredFormatter
logging_formatter = ColoredFormatter(
    "%(purple)s%(asctime)s%(reset)s - %(log_color)s%(levelname)s%(reset)s - %(white)s%(message)s%(reset)s",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
    }
)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging_formatter)
logger.addHandler(stream_handler)

from SupportMeshCreator import SupportMeshCreator
from MeshPretransformer import MeshPretransformer

def flipYZ(tri_mesh):
    tri_mesh.vertices[:,[2,1]] = tri_mesh.vertices[:,[1,2]]

def tempFileName():
    return os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names())) + ".stl"

def main():
    parser = argparse.ArgumentParser(description="Belt-style printer pre- and postprocessor for CuraEngine.")
    parser.add_argument("-v", action="store_true", help="show verbose messages")
    parser.add_argument("-x", type=str, nargs=1, help="CuraEngine executable path")
    parser.add_argument("-c", type=str, nargs="?", help="config file")
    parser.add_argument("-s", type=str, nargs=1, action="append", help="settings")
    parser.add_argument("-o", type=str, nargs=1, help="gcode output file")
    parser.add_argument("model.stl", type=str, nargs=1, help="stl model file to slice")

    known_args = vars(parser.parse_known_args()[0])
    if (known_args["v"]):
        logger.setLevel(logging.DEBUG)

    # get CuraEngine executable
    if (known_args["x"]):
        engine_path = known_args["x"]
    else:
        if sys.platform == "win32":
            engine_path = "bin/windows/CuraEngine.exe"
        elif sys.platform == "linux":
            engine_path = "bin/linux/CuraEngine"
        elif sys.platform == "darwin":
            engine_path = "bin/osx/CuraEngine"
        else:
            logger.error("Unsupported platform: %s" % sys.platform)
            return 1
    engine_path = os.path.abspath(engine_path)
    if not os.path.exists(engine_path):
        logger.error("CuraEngine executable not found: %s" % engine_path)
        return 1
    else:
        logger.info("Using CuraEngine from %s" % engine_path)

    # parse config file and command-line settings
    settings = OrderedDict()
    if known_args["c"]:
        config_file_path = os.path.abspath(known_args["c"])
        if not os.path.exists(config_file_path):
            logger.error("Specified config file not found: %s" % config_file_path)
            return 1

        logger.debug("Reading settings from %s" % config_file_path)
        with open(config_file_path) as config_file_pointer:
            config_file_content = config_file_pointer.read()
        if "[profile]" not in config_file_content:
            config_file_content = "[profile]\n" + config_file_content

        config_parser = configparser.ConfigParser()
        config_parser.read_string(config_file_content)
        settings = OrderedDict(config_parser["profile"])

    if known_args["s"]:
        commandline_settings = [tuple(setting_str[0].split("=", 1)) for setting_str in known_args["s"]]
        for key, value in commandline_settings:
            settings[key] = value

    # TODO: use dictionary of doom to convert legacy to current settings
    logger.debug("Settings: %s" % ", ".join(["%s:%s" % (s, settings[s]) for s in settings]))

    # TODO: use settings
    support_mesh_creator = SupportMeshCreator()
    mesh_pretransformer = MeshPretransformer()

    mesh_file_path = os.path.abspath(known_args["model.stl"][0])
    if not os.path.exists(mesh_file_path):
        logger.error("Specified model file not found: %s" % mesh_file_path)
        return 1

    logger.info("Loading mesh %s" % mesh_file_path)
    input_mesh = trimesh.load(mesh_file_path)
    flipYZ(input_mesh)
    input_mesh.fix_normals()

    input_bounds = input_mesh.bounds
    input_mesh.visual.vertex_colors = [[255,201,36,255]] * len(input_mesh.vertices)

    logger.info("Moving mesh to the start of the belt")
    input_mesh.apply_transform(trimesh.transformations.translation_matrix([
        (input_bounds[0][0] + input_bounds[1][0]) / -2.0,
        -input_bounds[0][1],
        -input_bounds[0][2]
    ]))

    logger.info("Create support mesh")
    support_mesh = support_mesh_creator.createSupportMesh(input_mesh)
    support_mesh.visual.vertex_colors = [[0,255,255,255]] * len(support_mesh.vertices)

    logger.info("Create raft mesh")
    raft_mesh_polygon = trimesh.path.polygons.projected(input_mesh.convex_hull, [0,1,0])
    raft_mesh = trimesh.creation.extrude_polygon(raft_mesh_polygon, -0.1)
    raft_mesh.vertices[:,[0,1,2]] = raft_mesh.vertices[:,[1,2,0]]
    raft_mesh.vertices[:,2] = -raft_mesh.vertices[:,2]
    raft_mesh.invert()
    raft_mesh.visual.vertex_colors = [[128,128,128,255]] * len(raft_mesh.vertices)

    if (known_args["v"]):
        (raft_mesh + support_mesh + input_mesh).show()

    logger.info("Creating temporary pretransformed mesh")
    flipYZ(input_mesh)
    input_mesh.invert()
    mesh_pretransformer.pretransformMesh(input_mesh)
    temp_mesh_file_path = tempFileName()
    input_mesh.export(temp_mesh_file_path)

    logger.info("Creating temporary pretransformed support-mesh")
    flipYZ(support_mesh)
    support_mesh.invert()
    mesh_pretransformer.pretransformMesh(support_mesh)
    temp_support_mesh_file_path = tempFileName()
    support_mesh.export(temp_support_mesh_file_path)

    logger.info("Creating temporary pretransformed raft-mesh")
    flipYZ(raft_mesh)
    raft_mesh.invert()
    mesh_pretransformer.pretransformMesh(raft_mesh)
    temp_raft_mesh_file_path = tempFileName()
    raft_mesh.export(temp_raft_mesh_file_path)

    logger.info("Launching CuraEngine")
    engine_args = [
        engine_path,
        "slice",
        "-j", os.path.join("resources","definitions","fdmprinter.def.json"),
        "-o", known_args["o"][0],
        "-l", temp_mesh_file_path
    ]
    for (key, value) in settings.items():
        engine_args.extend(["-s", "%s=%s" % (key, value)])
    engine_args.extend(["-l", temp_support_mesh_file_path])
    engine_args.extend(["-s",  "support_mesh=true"])
    engine_args.extend(["-l", temp_raft_mesh_file_path])
    # TODO: raft mesh settings

    output = subprocess.check_output(engine_args)
    logger.debug(output)

    os.remove(temp_mesh_file_path)
    os.remove(temp_support_mesh_file_path)
    os.remove(temp_raft_mesh_file_path)

if __name__ == "__main__":
    sys.exit(main())