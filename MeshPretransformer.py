# Copyright (c) 2020 Autodrop3D and Aldo Hoeben / fieldOfView
# BeltEngine is released under the terms of the AGPLv3 or higher.

import numpy
import math
import trimesh

class MeshPretransformer():
    def __init__(self,
                 gantry_angle = math.radians(45),
                 machine_depth = 99999,
            ):

        matrix = numpy.identity(4)
        matrix[:,1] = [0, 1 / math.tan(gantry_angle), 1, (machine_depth / 2) * (1 - math.cos(gantry_angle))]
        matrix[:,2] = [0, - 1 / math.sin(gantry_angle), 0, machine_depth / 2]

        # The above magic transform matrix is composed as follows:
        """
        matrix_data = numpy.identity(4)
        matrix_data[2, 2] = 1/math.sin(gantry_angle)  # scale Z
        matrix_data[1, 2] = -1/math.tan(gantry_angle) # shear ZY
        matrix = Matrix(matrix_data)
        matrix_data = numpy.identity(4)
        # use front buildvolume face instead of bottom face
        matrix_data[1, 1] = 0
        matrix_data[1, 2] = 1
        matrix_data[2, 1] = -1
        matrix_data[2, 2] = 0
        axes_matrix = Matrix(matrix_data)
        matrix.multiply(axes_matrix)
        # bottom face has origin at the center, front face has origin at one side
        matrix.translate(Vector(0, - math.sin(gantry_angle) * machine_depth / 2, 0))
        # make sure objects are not transformed to be below the buildplate
        matrix.translate(Vector(0, 0, machine_depth / 2))
        """
        self._pretransform_matrix = matrix

    def pretransformMesh(self, tri_mesh):
        tri_mesh.apply_transform(self._pretransform_matrix)