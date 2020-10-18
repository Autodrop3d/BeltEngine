#!/usr/bin/env python3

# Copyright (c) 2020 Autodrop3D and Aldo Hoeben / fieldOfView
# BeltEngine is released under the terms of the AGPLv3 or higher.

import sys
import os
import argparse
import trimesh
import shapely
import math
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

from SettingsParser import SettingsParser
from SupportMeshCreator import SupportMeshCreator
from MeshPretransformer import MeshPretransformer
from GcodePostProcessor import GcodePostProcessor

def flipYZ(tri_mesh):
    tri_mesh.vertices[:,[2,1]] = tri_mesh.vertices[:,[1,2]]

def tempFileName():
    return os.path.join(tempfile.gettempdir(), next(tempfile._get_candidate_names())) + ".stl"

def main():
    parser = argparse.ArgumentParser(description="Belt-style printer pre- and postprocessor for CuraEngine.")
    parser.add_argument("-v", action="store_true", help="show verbose messages")
    parser.add_argument("-x", type=str, nargs=1, help="CuraEngine executable path")
    parser.add_argument("-c", type=str, nargs=1, action="append", help="config file")
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

    settings_parser = SettingsParser(known_args["c"], known_args["s"])
    settings = settings_parser.getNonDefaultValues()
    logger.debug("Settings: %s" % ", ".join(["%s:%s" % (s, settings[s]) for s in settings]))

    # get belt slicing settings
    beltengine_gantry_angle = math.radians(float(settings_parser.getSettingValue("beltengine_gantry_angle")))

    beltengine_raft_enable = settings_parser.getSettingValue("beltengine_raft_enable")
    beltengine_raft_margin = settings_parser.getSettingValue("beltengine_raft_margin")
    beltengine_raft_thickness = settings_parser.getSettingValue("beltengine_raft_thickness")
    beltengine_raft_gap = settings_parser.getSettingValue("beltengine_raft_gap")
    beltengine_raft_speed = settings_parser.getSettingValue("beltengine_raft_speed")
    beltengine_raft_flow = settings_parser.getSettingValue("beltengine_raft_flow") * math.sin(beltengine_gantry_angle)

    beltengine_belt_wall_enable = settings_parser.getSettingValue("beltengine_belt_wall_enable")
    beltengine_belt_wall_speed = settings_parser.getSettingValue("beltengine_belt_wall_speed")
    beltengine_belt_wall_flow = settings_parser.getSettingValue("beltengine_belt_wall_flow") * math.sin(beltengine_gantry_angle)

    support_enable = settings_parser.getSettingValue("support_enable")
    beltengine_support_gantry_angle_bias = math.radians(settings_parser.getSettingValue("beltengine_support_gantry_angle_bias"))
    beltengine_support_minimum_island_area = settings_parser.getSettingValue("beltengine_support_minimum_island_area")

    settings_parser.setSettingValue("support_enable", "False")
    settings_parser.setSettingValue("adhesion_type", "\"none\"")
    for key in ["layer_height", "layer_height_0"]:
        settings_parser.setSettingValue(key, settings_parser.getSettingValue(key) / math.sin(beltengine_gantry_angle))
    for key in ["wall_0_material_flow", "wall_x_material_flow", "skin_material_flow", "roofing_material_flow", "infill_material_flow", "skirt_brim_material_flow", "support_material_flow", "support_roof_material_flow", "support_bottom_material_flow"]:
        settings_parser.setSettingValue(key, settings_parser.getSettingValue(key) * math.sin(beltengine_gantry_angle))

    mesh_pretransformer = MeshPretransformer(
        gantry_angle=beltengine_gantry_angle,
        machine_depth=settings_parser.getSettingValue("machine_depth")
    )

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

    support_mesh = None
    if support_enable:
        logger.info("Create support mesh")
        support_mesh_creator = SupportMeshCreator(
            support_angle=settings_parser.getSettingValue("support_angle"),
            filter_upwards_facing_faces=True,
            down_vector=[0, -math.cos(math.radians(beltengine_support_gantry_angle_bias)), -math.sin(beltengine_support_gantry_angle_bias)],
            bottom_cut_off=settings_parser.getSettingValue("wall_line_width_0"),
            minimum_island_area=beltengine_support_minimum_island_area
        )

        support_mesh = support_mesh_creator.createSupportMesh(input_mesh)
        support_mesh.visual.vertex_colors = [[0,255,255,255]] * len(support_mesh.vertices)

    raft_mesh = None
    if beltengine_raft_enable:
        logger.info("Create raft mesh")
        raft_mesh_polygon = trimesh.path.polygons.projected(input_mesh.convex_hull, [0,1,0])
        if beltengine_raft_margin > 0:
            offset_raft_mesh_points = raft_mesh_polygon.exterior.parallel_offset(beltengine_raft_margin, side="left", resolution=5)
            raft_mesh_polygon = shapely.geometry.Polygon(offset_raft_mesh_points)
        elif beltengine_raft_margin < 0:
            offset_raft_mesh_points = raft_mesh_polygon.exterior.parallel_offset(-beltengine_raft_margin, side="right", resolution=5)
            raft_mesh_polygon = shapely.geometry.Polygon(offset_raft_mesh_points)
        raft_mesh = trimesh.creation.extrude_polygon(raft_mesh_polygon, -beltengine_raft_thickness)
        raft_mesh.vertices[:,[0,1,2]] = -raft_mesh.vertices[:,[1,2,0]]
        raft_mesh.invert()
        raft_mesh.visual.vertex_colors = [[128,128,128,255]] * len(raft_mesh.vertices)

        translation_for_raft = trimesh.transformations.translation_matrix([
            0, beltengine_raft_thickness + beltengine_raft_gap, 0
        ])
        input_mesh.apply_transform(translation_for_raft)
        if support_mesh:
            support_mesh.apply_transform(translation_for_raft)

    if (known_args["v"]):
        show_mesh = input_mesh.copy()
        if support_enable:
            show_mesh += support_mesh
        if raft_mesh:
            show_mesh += raft_mesh

        show_mesh.show()

    logger.info("Creating temporary pretransformed mesh")
    flipYZ(input_mesh)
    input_mesh.invert()
    mesh_pretransformer.pretransformMesh(input_mesh)
    temp_mesh_file_path = tempFileName()
    input_mesh.export(temp_mesh_file_path)

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

    if support_enable:
        logger.info("Creating temporary pretransformed support-mesh")
        flipYZ(support_mesh)
        support_mesh.invert()
        mesh_pretransformer.pretransformMesh(support_mesh)
        temp_support_mesh_file_path = tempFileName()
        support_mesh.export(temp_support_mesh_file_path)

        engine_args.extend(["-l", temp_support_mesh_file_path])
        engine_args.extend(["-s",  "support_mesh=true"])
        engine_args.extend(["-s",  "support_mesh_drop_down=false"])

    if beltengine_raft_enable:
        logger.info("Creating temporary pretransformed raft-mesh")
        flipYZ(raft_mesh)
        raft_mesh.invert()
        mesh_pretransformer.pretransformMesh(raft_mesh)
        temp_raft_mesh_file_path = tempFileName()
        raft_mesh.export(temp_raft_mesh_file_path)

        engine_args.extend(["-l", temp_raft_mesh_file_path])
        engine_args.extend(["-s", "wall_line_count=99999999"])
        engine_args.extend(["-s", "speed_wall_0=%f" % beltengine_raft_speed])
        engine_args.extend(["-s", "speed_wall_x=%f" % beltengine_raft_speed])
        engine_args.extend(["-s", "material_flow=%f" % beltengine_raft_flow])

    logger.debug(engine_args)

    process = subprocess.Popen(engine_args, stdout=subprocess.PIPE)
    for line in process.stdout:
        logger.debug(line)

    logger.info("Removing temporary meshes")
    os.remove(temp_mesh_file_path)
    if support_enable:
        os.remove(temp_support_mesh_file_path)
    if beltengine_raft_enable:
        os.remove(temp_raft_mesh_file_path)

    if beltengine_belt_wall_enable:
        logger.info("Post processing gcode for belt wall")

        post_processor = GcodePostProcessor(
            belt_wall_enable=beltengine_belt_wall_enable,
            belt_wall_flow=beltengine_belt_wall_flow,
            belt_wall_speed=beltengine_belt_wall_speed,
            wall_line_width_0=settings_parser.getSettingValue("wall_line_width_0")
        )
        post_processor.processGcodeFile(known_args["o"][0])

if __name__ == "__main__":
    sys.exit(main())