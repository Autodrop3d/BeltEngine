# Copyright (c) 2020 Autodrop3D and Aldo Hoeben / fieldOfView
# BeltEngine is released under the terms of the AGPLv3 or higher.

import numpy
import trimesh
import shapely
import math

import logging
logger = logging.getLogger("BeltEngine")

def createSupportMesh(
        tri_mesh,
        support_angle = 50,
        filter_upwards_facing_faces = True,
        down_vector = numpy.array([0, -1, 0]),
        bottom_cut_off = 0,
        minimum_island_area = 0
    ):
    mesh_vertices = tri_mesh.vertices
    mesh_indices = tri_mesh.faces
    cos_support_angle = math.cos(math.radians(90 - support_angle))

    # get indices of faces that face down more than support_angle
    cos_angle_between_normal_down = numpy.dot(tri_mesh.face_normals, down_vector)
    faces_needing_support = numpy.argwhere(cos_angle_between_normal_down >= cos_support_angle).flatten()
    # filter out faces that point upwards
    if len(faces_needing_support) == 0 and filter_upwards_facing_faces:
        faces_facing_down = numpy.argwhere(tri_mesh.face_normals[:,1] < 0)
        faces_needing_support = numpy.intersect1d(faces_facing_down, faces_needing_support)
    if len(faces_needing_support) == 0:
        logger.info("Mesh doesn't need support")
        return trimesh.Trimesh()
    roof_indices = mesh_indices[faces_needing_support]

    # filter out faces that are coplanar with the bottom
    non_bottom_indices = numpy.where(numpy.any(mesh_vertices[roof_indices].take(1, axis=2) > bottom_cut_off, axis=1))[0].flatten()
    roof_indices = roof_indices[non_bottom_indices]
    if len(roof_indices) == 0:
        logger.info("Mesh doesn't need support")
        return trimesh.Trimesh()

    roof = trimesh.base.Trimesh(vertices=mesh_vertices, faces=roof_indices)
    roof.remove_unreferenced_vertices()
    roof.process()

    if minimum_island_area > 0:
        # filter out all islands that would result in small towers
        scale_matrix = trimesh.transformations.scale_matrix(0, direction=[0,1,0])
        roof_elements = roof.split(only_watertight=False)
        roof = trimesh.base.Trimesh()
        for roof_element in roof_elements:
            xy_element = roof_element.copy()
            xy_element.apply_transform(scale_matrix)
            if xy_element.area >= minimum_island_area:
                roof = roof + roof_element

    num_roof_vertices = len(roof.vertices)
    if num_roof_vertices == 0:
        logger.info("All surfaces of the mesh that need support are smaller than the minimum_island_area")
        return trimesh.Trimesh()

    connecting_faces = []

    roof_outline = roof.outline()
    for entity in roof_outline.entities:
        entity_points = entity.points
        outline = roof_outline.vertices[entity_points]

        # numpy magic to find indices for each outline vertex
        outline_indices = numpy.where((roof.vertices==outline[:,None]).all(-1))[1]

        num_outline_vertices = len(outline)
        for i in range(0, num_outline_vertices - 1):
            connecting_faces.append([outline_indices[i], outline_indices[i + 1] + num_roof_vertices, outline_indices[i] + num_roof_vertices])
            connecting_faces.append([outline_indices[i], outline_indices[i + 1], outline_indices[i + 1] + num_roof_vertices])

    support_vertices = numpy.concatenate((roof.vertices, roof.vertices * [1,0,1]))
    support_faces = numpy.concatenate((roof.faces, roof.faces + len(roof.vertices), connecting_faces))

    support_mesh = trimesh.base.Trimesh(vertices=support_vertices, faces=support_faces)
    support_mesh.fix_normals()

    return support_mesh

def createRaftMesh(
        tri_mesh,
        raft_thickness=0.1,
        raft_margin=0
    ):

    raft_mesh_polygon = trimesh.path.polygons.projected(tri_mesh.convex_hull, [0,1,0])
    if raft_margin > 0:
        offset_raft_mesh_points = raft_mesh_polygon.exterior.parallel_offset(raft_margin, side="left", resolution=5)
        raft_mesh_polygon = shapely.geometry.Polygon(offset_raft_mesh_points)
    elif raft_margin < 0:
        offset_raft_mesh_points = raft_mesh_polygon.exterior.parallel_offset(-raft_margin, side="right", resolution=5)
        raft_mesh_polygon = shapely.geometry.Polygon(offset_raft_mesh_points)
    raft_mesh = trimesh.creation.extrude_polygon(raft_mesh_polygon, -raft_thickness)
    raft_mesh.vertices[:,[0,1,2]] = -raft_mesh.vertices[:,[1,2,0]]
    raft_mesh.invert()

    return raft_mesh