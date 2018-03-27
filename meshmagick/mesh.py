#!/usr/bin/env python
#  -*- coding: utf-8 -*-
"""
This module concerns mesh data structures.

TODO: mettre des examples d'utilisation
"""


import numpy as np
import math
import copy
import vtk
from itertools import count
from warnings import warn

from meshmagick.tools import merge_duplicate_rows
from meshmagick.inertia import RigidBodyInertia
from meshmagick.geometry import Plane
from meshmagick.MMviewer import MMViewer

__author__ = "Francois Rongere"
__copyright__ = "Copyright 2014-2015, Ecole Centrale de Nantes"
__credits__ = "Francois Rongere"
__licence__ = "CeCILL"
__maintainer__ = "Francois Rongere"
__email__ = "Francois.Rongere@ec-nantes.fr"
__status__ = "Development"

# TODO: Use traitlets to manage updates into the Mesh class
# TODO: les points doivent etre des objects nodes...
# TODO: On doit pouvoir specifier des objets frame


class Mesh(object):
    """A class to handle unstructured meshes.

    Parameters
    ----------
    vertices : array_like
        (nv x 3) Array of mesh vertices coordinates. Each line of the array represents one vertex coordinates
    faces : array_like
        Arrays of mesh connectivities for faces. Each line of the array represents indices of vertices that form the
        face, expressed in counterclockwise order to ensure outward normals description.
    name : str, optional
        The mesh's name. If None, mesh is given an automatic name based on its internal ID.
    """
    _ids = count(0)
    
    def __init__(self, vertices, faces, name=None):

        self.__internals__ = dict()
        
        assert np.array(vertices).shape[1] == 3
        assert np.array(faces).shape[1] == 4
        
        self._vertices = np.array(vertices, dtype=np.float)
        self._faces = np.array(faces, dtype=np.int)
        self._id = next(self._ids)

        if not name:
            self._name = 'mesh_%u' % self._id
        else:
            self._name = str(name)

        self._verbose = False

    def __str__(self):
        """String representation of the mesh
        
        Returns
        -------
        str
        """
        xmin, xmax, ymin, ymax, zmin, zmax = self.axis_aligned_bbox
        
        str_repr = """
        --------------------------------------------
        \tMESH NAME : %s
        --------------------------------------------

        Number of vertices: %u
        Number of faces:    %u

        Number of triangles:   %u
        Number of quadrangles: %u

        xmin = %f\txmax = %f
        ymin = %f\tymax = %f
        zmin = %f\tzmax = %f


        """ % (self.name,
               self.nb_vertices,
               self.nb_faces,
               self.nb_triangles,
               self.nb_quadrangles,
               xmin, xmax,
               ymin, ymax,
               zmin, zmax
               )
        return str_repr

    def print_quality(self):
        """Returns data on the mesh quality
        
        It uses VTK and is reproduced from
        http://vtk.org/gitweb?p=VTK.git;a=blob;f=Filters/Verdict/Testing/Python/MeshQuality.py
        """
        # This function is reproduced from
        # http://vtk.org/gitweb?p=VTK.git;a=blob;f=Filters/Verdict/Testing/Python/MeshQuality.py
        polydata = self._vtk_polydata()
        quality = vtk.vtkMeshQuality()
        if vtk.VTK_MAJOR_VERSION <= 5:
            quality.SetInput(polydata)
        else:
            quality.SetInputData(polydata)

        def DumpQualityStats(iq, arrayname):
            an = iq.GetOutput().GetFieldData().GetArray(arrayname)
            cardinality = an.GetComponent(0, 4)
            range = list()
            range.append(an.GetComponent(0, 0))
            range.append(an.GetComponent(0, 2))
            average = an.GetComponent(0, 1)
            stdDev = math.sqrt(math.fabs(an.GetComponent(0, 3)))
            outStr = '%s%g%s%g\n%s%g%s%g' % (
                '    range: ', range[0], '  -  ', range[1],
                '    average: ', average, '  , standard deviation: ', stdDev)
            return outStr

        # Here we define the various mesh types and labels for output.
        meshTypes = [
            ['Triangle', 'Triangle',
             [['QualityMeasureToArea', ' Area Ratio:'],
              ['QualityMeasureToEdgeRatio', ' Edge Ratio:'],
              ['QualityMeasureToAspectRatio', ' Aspect Ratio:'],
              ['QualityMeasureToRadiusRatio', ' Radius Ratio:'],
              ['QualityMeasureToAspectFrobenius', ' Frobenius Norm:'],
              ['QualityMeasureToMinAngle', ' Minimal Angle:']
              ]
             ],

            ['Quad', 'Quadrilateral',
             [['QualityMeasureToArea', ' Area Ratio:'],
              ['QualityMeasureToEdgeRatio', ' Edge Ratio:'],
              ['QualityMeasureToAspectRatio', ' Aspect Ratio:'],
              ['QualityMeasureToRadiusRatio', ' Radius Ratio:'],
              ['QualityMeasureToMedAspectFrobenius',
               ' Average Frobenius Norm:'],
              ['QualityMeasureToMaxAspectFrobenius',
               ' Maximal Frobenius Norm:'],
              ['QualityMeasureToMinAngle', ' Minimal Angle:']
              ]
             ]
        ]
        res = ''
        if polydata.GetNumberOfCells() > 0:
            for meshType in meshTypes:
                res += '\n%s%s' % (meshType[1], ' quality of the mesh ')
                quality.Update()
                an = quality.GetOutput().GetFieldData().GetArray('Mesh ' + meshType[1] + ' Quality')
                cardinality = an.GetComponent(0, 4)

                res = ''.join((res, '(%u elements):\n' % cardinality))

                # res += '('+str(cardinality) +meshType[1]+'):\n'

                for measure in meshType[2]:
                    eval('quality.Set' + meshType[0] + measure[0] + '()')
                    quality.Update()
                    res += '\n%s\n%s' % (
                        measure[1],
                        DumpQualityStats(quality, 'Mesh ' + meshType[1] + ' Quality')
                    )
                res += '\n'

        info = """\n\nDefinition of the different quality measures is given
        in the verdict library manual :
        http://www.vtk.org/Wiki/images/6/6b/VerdictManual-revA.pdf\n"""

        res += info
        print(res)
        return

    @property
    def verbose(self):
        """Get verbosity
        
        Returns
        -------
        bool
        """
        return self._verbose

    @verbose.setter
    def verbose(self, value):
        self._verbose = bool(value)
        return

    def verbose_on(self):
        """Set the verbosity level of the instance to on."""
        self._verbose = True
        return

    def verbose_off(self):
        """Set the verbosity level of the instance to off."""
        self._verbose = False
        return

    @property
    def id(self):
        """Get the id of the mesh
        
        Returns
        -------
        int
            hash id of the instance
        """
        return self._id

    @property
    def name(self):
        """Get the name of the mesh"""
        return self._name

    @name.setter
    def name(self, value):
        self._name = str(value)
        return

    @property
    def nb_vertices(self):
        """Get the number of vertices in the mesh
        
        Returns
        -------
        int
        """
        return self._vertices.shape[0]

    @property
    def nb_faces(self):
        """Get the number of faces in the mesh
        
        Returns
        -------
        int
        """
        return self._faces.shape[0]

    @property
    def vertices(self):
        """Get the vertices array coordinate of the mesh
        
        Returns
        -------
        ndarray
        """
        return self._vertices

    @property
    def faces(self):
        """Get the faces connectivity array of the mesh
        
        Returns
        -------
        ndarray
        """
        return self._faces

    @vertices.setter
    def vertices(self, value):
        self._vertices = np.asarray(value, dtype=np.float).copy()
        # self._vertices.setflags(write=False)
        self.__internals__.clear()
        return

    @faces.setter
    def faces(self, value):
        self._faces = np.asarray(value, dtype=np.int).copy()
        # self._faces.setflags(write=False)
        self.__internals__.clear()
        return

    def _faces_properties(self):
        """Updates the faces properties of the mesh"""
        
        # faces_areas, faces_normals, faces_centers = mm.get_all_faces_properties(self._vertices, self._faces)
        nf = self.nb_faces

        # triangle_mask = _faces[:, 0] == _faces[:, -1]
        # nb_triangles = np.sum(triangle_mask)
        # quads_mask = np.invert(triangle_mask)
        # nb_quads = nf - nb_triangles

        faces_areas = np.zeros(nf, dtype=np.float)
        faces_normals = np.zeros((nf, 3), dtype=np.float)
        faces_centers = np.zeros((nf, 3), dtype=np.float)

        # Collectively dealing with triangles
        # triangles = _faces[triangle_mask]
        triangles_id = self.triangles_ids
        triangles = self._faces[triangles_id]

        triangles_normals = np.cross(self._vertices[triangles[:, 1]] - self._vertices[triangles[:, 0]],
                                     self._vertices[triangles[:, 2]] - self._vertices[triangles[:, 0]])
        triangles_areas = np.linalg.norm(triangles_normals, axis=1)
        faces_normals[triangles_id] = triangles_normals / np.array(([triangles_areas, ] * 3)).T
        faces_areas[triangles_id] = triangles_areas / 2.
        faces_centers[triangles_id] = np.sum(self._vertices[triangles[:, :3]], axis=1) / 3.

        # Collectively dealing with quads
        quads_id = self.quadrangles_ids
        quads = self._faces[quads_id]
        # quads = _faces[quads_mask]

        quads_normals = np.cross(self._vertices[quads[:, 2]] - self._vertices[quads[:, 0]],
                                 self._vertices[quads[:, 3]] - self._vertices[quads[:, 1]])
        faces_normals[quads_id] = quads_normals / np.array(([np.linalg.norm(quads_normals, axis=1), ] * 3)).T

        a1 = np.linalg.norm(np.cross(self._vertices[quads[:, 1]] - self._vertices[quads[:, 0]],
                                     self._vertices[quads[:, 2]] - self._vertices[quads[:, 0]]), axis=1) * 0.5
        a2 = np.linalg.norm(np.cross(self._vertices[quads[:, 3]] - self._vertices[quads[:, 0]],
                                     self._vertices[quads[:, 2]] - self._vertices[quads[:, 0]]), axis=1) * 0.5
        faces_areas[quads_id] = a1 + a2
        
        c1 = np.sum(self._vertices[quads[:, :3]], axis=1) / 3.
        c2 = (np.sum(self._vertices[quads[:, 2:4]], axis=1) + self._vertices[quads[:, 0]]) / 3.

        faces_centers[quads_id] = (np.array(([a1, ] * 3)).T * c1 + np.array(([a2, ] * 3)).T * c2)
        faces_centers[quads_id] /= np.array(([faces_areas[quads_id], ] * 3)).T

        faces_properties = {'faces_areas': faces_areas,
                            'faces_normals': faces_normals,
                            'faces_centers': faces_centers}

        self.__internals__.update(faces_properties)

        return

    def _has_faces_properties(self):
        return 'faces_areas' in self.__internals__

    def _remove_faces_properties(self):
        if self._has_faces_properties():
            del self.__internals__['faces_areas']
            del self.__internals__['faces_centers']
            del self.__internals__['faces_normals']
        if self.has_surface_integrals():
            del self.__internals__['surface_integrals']
        return

    @property
    def faces_areas(self):
        """Get the array of faces areas of the mesh
        
        Returns
        -------
        ndarray
        """
        if 'faces_areas' not in self.__internals__:
            self._faces_properties()
        return self.__internals__['faces_areas']

    @property
    def faces_centers(self):
        """Get the array of faces centers of the mesh
        
        Returns
        -------
        ndarray
        """
        if 'faces_centers' not in self.__internals__:
            self._faces_properties()
        return self.__internals__['faces_centers']

    @property
    def faces_normals(self):
        """Get the array of faces normals of the mesh

        Returns
        -------
        ndarray
        """
        if 'faces_normals' not in self.__internals__:
            self._faces_properties()
        return self.__internals__['faces_normals']

    @property
    def faces_radiuses(self):
        """Get the array of faces radiuses of the mesh.
        
        Returns
        -------
        ndarray
        """
        if 'faces_radiuses' not in self.__internals__:
            self._compute_radiuses()
        return self.__internals__['faces_radiuses']

    def _compute_radiuses(self):
        """Compute the radiuses of the faces of the mesh.

        The radius is defined here as the maximal distance between the center
        of mass of a cell and one of its points."""

        # Coordinates of all the vertices grouped by face
        faces_vertices = self.vertices[self.faces, :]
        # faces_vertices.shape == (nb_faces, 4, 3)

        # Reorder the axes for array broadcasting below
        faces_vertices = np.moveaxis(faces_vertices, 0, 1)
        # faces_vertices.shape == (4, nb_faces, 3)

        # Get all the vectors between the center of faces and their vertices.
        radial_vector = self.faces_centers - faces_vertices
        # radial_vector.shape == (4, nb_faces, 3)

        # Keep the maximum length
        faces_radiuses = np.max(np.linalg.norm(radial_vector, axis=2), axis=0)
        # faces_radiuses.shape = (nb_faces)

        self.__internals__["faces_radiuses"] = faces_radiuses

    def _triangles_quadrangles(self):
        triangle_mask = (self._faces[:, 0] == self._faces[:, -1])
        quadrangles_mask = np.invert(triangle_mask)
        triangles_quadrangles = {'triangles_ids': np.where(triangle_mask)[0],
                                 'quadrangles_ids': np.where(quadrangles_mask)[0]}
        self.__internals__.update(triangles_quadrangles)
        return

    def _has_triangles_quadrangles(self):
        return 'triangles_ids' in self.__internals__

    def _remove_triangles_quadrangles(self):
        if 'triangles_ids' in self.__internals__:
            del self.__internals__['triangles_ids']
            del self.__internals__['quadrangles_ids']
        return

    @property
    def triangles_ids(self):
        """Get the array of ids of triangle shaped faces
        
        Returns
        -------
        ndarray
        """
        if 'triangles_ids' not in self.__internals__:
            self._triangles_quadrangles()
        return self.__internals__['triangles_ids']

    @property
    def nb_triangles(self):
        """Get the number of triangles in the mesh
        
        Returns
        -------
        int
        """
        if 'triangles_ids'not in self.__internals__:
            self._triangles_quadrangles()
        return len(self.__internals__['triangles_ids'])

    @property
    def quadrangles_ids(self):
        """Get the array of ids of quadrangle shaped faces

        Returns
        -------
        ndarray
        """
        if 'triangles_ids' not in self.__internals__:
            self._triangles_quadrangles()
        return self.__internals__['quadrangles_ids']

    @property
    def nb_quadrangles(self):
        """Get the number of quadrangles in the mesh

        Returns
        -------
        int
        """
        if 'triangles_ids' not in self.__internals__:
            self._triangles_quadrangles()
        return len(self.__internals__['quadrangles_ids'])

    def is_triangle(self, face_id):
        """Returns if a face is a triangle
        
        Parameters
        ----------
        face_id : int
            Face id

        Returns
        -------
        bool
            True if the face with id face_id is a triangle
        """
        assert 0 <= face_id < self.nb_faces
        return self._faces[face_id, 0] == self._faces[face_id, -1]

    def get_face(self, face_id):
        """Get the face described by its vertices connectivity
        
        Parameters
        ----------
        face_id : int
            Face id

        Returns
        -------
        ndarray
            If the face is a triangle, the array has 3 components, else it has 4 (quadrangle)
        """
        if self.is_triangle(face_id):
            return self._faces[face_id, :3]
        else:
            return self._faces[face_id]

    def extract_faces(self, id_faces_to_extract, return_index=False):
        """
        Extracts a new mesh from a selection of faces ids

        Parameters
        ----------
        id_faces_to_extract : ndarray
            Indices of faces that have to be extracted
        return_index: bool
            Flag to output old indices

        Returns
        -------
        Mesh
            A new Mesh instance composed of the extracted faces
        """
        nv = self.nb_vertices

        # Determination of the vertices to keep
        vertices_mask = np.zeros(nv, dtype=bool)
        vertices_mask[self._faces[id_faces_to_extract].flatten()] = True
        id_v = np.arange(nv)[vertices_mask]

        # Building up the vertex array
        v_extracted = self._vertices[id_v]
        new_id__v = np.arange(nv)
        new_id__v[id_v] = np.arange(len(id_v))

        faces_extracted = self._faces[id_faces_to_extract]
        faces_extracted = new_id__v[faces_extracted.flatten()].reshape((len(id_faces_to_extract), 4))

        extracted_mesh = Mesh(v_extracted, faces_extracted)
        extracted_mesh._verbose = self._verbose

        extracted_mesh.name = 'mesh_extracted_from_%s' % self.name

        if return_index:
            return extracted_mesh, id_v
        else:
            return extracted_mesh

    def _vtk_polydata(self):
        # TODO: placer cette methode dans MMviewer !!
        # Create a vtkPoints object and store the points in it
        points = vtk.vtkPoints()
        for point in self.vertices:
            points.InsertNextPoint(point)

        # Create a vtkCellArray to store faces
        faces = vtk.vtkCellArray()
        for face_ids in self.faces:
            if face_ids[0] == face_ids[-1]:
                # Triangle
                curface = face_ids[:3]
                vtk_face = vtk.vtkTriangle()
            else:
                # Quadrangle
                curface = face_ids[:4]
                vtk_face = vtk.vtkQuad()

            for idx, id in enumerate(curface):
                vtk_face.GetPointIds().SetId(idx, id)

            faces.InsertNextCell(vtk_face)

        vtk_polydata = vtk.vtkPolyData()
        vtk_polydata.SetPoints(points)
        vtk_polydata.SetPolys(faces)

        return vtk_polydata

    def show(self):
        """Shows the mesh in the meshmagick viewer"""
        
        vtk_polydata = self._vtk_polydata()
        self.viewer = MMViewer()
        self.viewer.add_polydata(vtk_polydata)
        self.viewer.show()
        self.viewer.finalize()

    def show_matplotlib(self, ax=None,
                        normal_vectors=False, scale_normal_vector=None,
                        **kwargs):
        """Poor man's viewer with matplotlib.

        Parameters
        ----------
        ax: matplotlib axis
            The 3d axis in which to plot the mesh. If not provided, create a new one.
        normal_vector: bool
            If True, print normal vector.
        scale_normal_vector: array of shape (nb_faces, )
            Scale separately each of the normal vectors.

        Other parameters are passed to Poly3DCollection.
        """
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        default_axis = ax is None
        if default_axis:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="3d")

        faces = []
        for face in self.faces:
            vertices = []
            for index_vertex in face:
                vertices.append(self.vertices[int(index_vertex), :])
            faces.append(vertices)
        if 'facecolors' not in kwargs:
            kwargs['facecolors'] = (0.3, 0.3, 0.3, 0.3)
        if 'edgecolor' not in kwargs:
            kwargs['edgecolor'] = 'k'
        ax.add_collection3d(Poly3DCollection(faces, **kwargs))

        # Plot normal vectors.
        if normal_vectors:
            if scale_normal_vector is not None:
                vectors = (scale_normal_vector * self.faces_normals.T).T
            else:
                vectors = self.faces_normals
            # NB: this is Python 3 only syntax...
            ax.quiver(*zip(*self.faces_centers), *zip(*vectors), length=0.2)

        if default_axis:
            ax.set_xlabel("x")
            ax.set_ylabel("y")

            # Dirty trick for orthonormal axes
            span = 1.05*max([max(self.vertices[:, j]) - min(self.vertices[:, j]) for j in range(3)])
            centers = [(max(self.vertices[:, j]) + min(self.vertices[:, j]))/2 for j in range(3)]
            ax.set_xlim(centers[0] - span/2, centers[0] + span/2)
            ax.set_ylim(centers[1] - span/2, centers[1] + span/2)
            ax.set_zlim(centers[2] - span/2, centers[2] + span/2)

            plt.show()

    def _connectivity(self):
        """Updates the connectivities of the mesh.
        
        It concerns further connectivity than simple faces/vertices connectivities. It computes the vertices / vertices, vertices / faces and faces / faces connectivities.
        
        Note
        ----
        
        Note that if the mesh is not conformal, the algorithm may not perform correctly
        """
        nv = self.nb_vertices
        nf = self.nb_faces

        mesh_closed = True

        # Building connectivities

        # Establishing v_v and v_f connectivities
        v_v = dict([(i, set()) for i in range(nv)])
        v_f = dict([(i, set()) for i in range(nv)])
        for (iface, face) in enumerate(self._faces):
            if face[0] == face[-1]:
                face_w = face[:3]
            else:
                face_w = face
            for (index, iV) in enumerate(face_w):
                v_f[iV].add(iface)
                v_v[face_w[index - 1]].add(iV)
                v_v[iV].add(face_w[index - 1])

        # Connectivity f_f
        boundary_edges = dict()

        f_f = dict([(i, set()) for i in range(nf)])
        for ivertex in range(nv):
            set1 = v_f[ivertex]
            for iadj_v in v_v[ivertex]:
                set2 = v_f[iadj_v]
                intersection = list(set1 & set2)
                if len(intersection) == 2:
                    f_f[intersection[0]].add(intersection[1])
                    f_f[intersection[1]].add(intersection[0])

                elif len(intersection) == 1:
                    boundary_face = self._faces[intersection[0]]

                    if boundary_face[0] == boundary_face[-1]:
                        boundary_face = boundary_face[:3]
                    ids = np.where((boundary_face == ivertex) + (boundary_face == iadj_v))[0]

                    if ids[1] != ids[0]+1:
                        i_v_orig, i_v_target = boundary_face[ids]
                    else:
                        i_v_target, i_v_orig = boundary_face[ids]

                    boundary_edges[i_v_orig] = i_v_target
                else:
                    raise RuntimeError('Unexpected error while computing mesh connectivities')

        # Computing boundaries
        boundaries = list()
        # TODO: calculer des boundaries fermees et ouvertes (closed_boundaries et open_boundaries) et mettre dans dict
        while True:
            try:
                boundary = list()
                i_v0_init, i_v1 = boundary_edges.popitem()
                boundary.append(i_v0_init)
                boundary.append(i_v1)
                i_v0 = i_v1

                while True:
                    try:
                        i_v1 = boundary_edges.pop(i_v0)
                        boundary.append(i_v1)
                        i_v0 = i_v1
                    except KeyError:
                        if boundary[0] != boundary[-1]:
                            print('Boundary is not closed !!!')
                        else:
                            boundaries.append(boundary)
                        break
            except KeyError:
                break

        connectivity = {'v_v': v_v,
                        'v_f': v_f,
                        'f_f': f_f,
                        'boundaries': boundaries}
        self.__internals__.update(connectivity)

        return

    def _has_connectivity(self):
        return 'v_v' in self.__internals__

    def _remove_connectivity(self):
        if 'v_v' in self.__internals__:
            del self.__internals__['v_v']
            del self.__internals__['v_f']
            del self.__internals__['f_f']
            del self.__internals__['boundaries']
        return

    @property
    def vv(self):
        """Get the vertex / vertex connectivity dictionary.
        
        Returns
        -------
        dict
        """
        if 'v_v' not in self.__internals__:
            self._connectivity()
        return self.__internals__['v_v']

    @property
    def vf(self):
        """Get the vertex / faces connectivity dictionary.
        
        Returns
        -------
        dict
        """
        if 'v_f' not in self.__internals__:
            self._connectivity()
        return self.__internals__['v_f']

    @property
    def ff(self):
        """Get the face / faces connectivity dictionary
        
        Returns
        -------
        dict
        """
        if 'f_f' not in self.__internals__:
            self._connectivity()
        return self.__internals__['f_f']

    @property
    def boundaries(self):
        """Get the list of boundaries of the mesh.
        
        Returns
        -------
        list
            list that stores lists of boundary connected vertices
        
        
        Note
        ----
        The computation of boundaries should be in the future computed with help of VTK
        """
        if 'boundaries' not in self.__internals__:
            self._connectivity()
        return self.__internals__['boundaries']

    @property
    def nb_boundaries(self):
        """Get the number of boundaries in the mesh
        
        Returns
        -------
        list
            Number of boundaries
        """
        if 'boundaries' not in self.__internals__:
            self._connectivity()
        return len(self.__internals__['boundaries'])
    
    @property
    def axis_aligned_bbox(self):
        """Get the axis aligned bounding box of the mesh.
        
        Returns
        -------
        tuple
            (xmin, xmax, ymin, ymax, zmin, zmax)
        """
        if self.nb_vertices > 0:
            x, y, z = self._vertices.T
            return (x.min(), x.max(),
                    y.min(), y.max(),
                    z.min(), z.max())
        else:
            return tuple(np.zeros(6))
    
    @property
    def squared_axis_aligned_bbox(self):
        """Get a squared axis aligned bounding box of the mesh.
        
        Returns
        -------
        tuple
            (xmin, xmax, ymin, ymax, zmin, zmax)
            
        Note
        ----
        This method differs from `axis_aligned_bbox()` by the fact that the bounding box that is returned is squared but have the same center as the AABB
        """
        xmin, xmax, ymin, ymax, zmin, zmax = self.axis_aligned_bbox
        (x0, y0, z0) = np.array([xmin+xmax, ymin+ymax, zmin+zmax]) * 0.5
        d = (np.array([xmax-xmin, ymax-ymin, zmax-zmin]) * 0.5).max()
        
        return x0-d, x0+d, y0-d, y0+d, z0-d, z0+d
    
    def is_mesh_closed(self):
        """Returns if the mesh is a closed manifold.
        
        Returns
        -------
        bool
            True if the mesh is closed (i.e. it has no boundaries)
        """
        if 'boundaries' not in self.__internals__:
            self._connectivity()
        return len(self.__internals__['boundaries']) == 0

    def is_mesh_conformal(self):
        """Returns if the mesh is conformal.
        
        Returns
        -------
        bool
            True if the mesh is conformal.
            
        Warning
        -------
        This method is experimental. Use at your own risk !
        """
        warn('This method is not stable yet !! Use with caution')
        # FIXME: experimental method
        tol = 1e-7
        
        if not self._has_connectivity():
            self._connectivity()
        
        boundaries = self.__internals__['boundaries']
        conformal = True

        for boundary in boundaries:
            boundary_vertices = self._vertices[boundary]
            # Si les trois projections (Oxy, Oxz, Oyz) de boundary sont des courbes dans ces plans, alors la courbe
            # est colapsee
            # Projecting on Oxy
            plane = Plane(normal=[0., 0., 1.])
            proj0 = plane.orthogonal_projection_on_plane(boundary_vertices)
            # Projecting on Oyz
            plane.normal = [1., 0., 0.]
            proj1 = plane.orthogonal_projection_on_plane(boundary_vertices)
            # Projecting on Oxz
            plane.normal = [0., 1., 0.]
            proj2 = plane.orthogonal_projection_on_plane(boundary_vertices)

            # Compputing areas of curves
            x = proj0[:, 0]
            y = proj0[:, 1]
            a0 = ((np.roll(y, -1)-y) * (np.roll(x, -1)+x)).sum()

            y = proj1[:, 0]
            z = proj1[:, 1]
            a1 = ((np.roll(y, -1)-y) * (np.roll(z, -1)+z)).sum()

            x = proj2[:, 0]
            z = proj2[:, 1]
            a2 = ((np.roll(x, -1)-x) * (np.roll(z, -1)+z)).sum()

            if math.fabs(a0) < tol and math.fabs(a1) < tol and math.fabs(a2) < tol:
                conformal = False

        return conformal

    def rotate_x(self, thetax):
        """Rotates the mesh around Ox axis.
        
        Parameters
        ----------
        thetax : float
            Angle (rad)

        Returns
        -------
        ndarray
            The (3x3) rotation matrix that has been applied to rotate the mesh
        """
        return self.rotate([thetax, 0., 0.])

    def rotate_y(self, thetay):
        """Rotates the mesh around Oy axis.

        Parameters
        ----------
        thetay : float
            Angle (rad)

        Returns
        -------
        ndarray
            The (3x3) rotation matrix that has been applied to rotate the mesh
        """
        return self.rotate([0., thetay, 0.])

    def rotate_z(self, thetaz):
        """Rotates the mesh around Oz axis.

        Parameters
        ----------
        thetaz : float
            Angle (rad)

        Returns
        -------
        ndarray
            The (3x3) rotation matrix that has been applied to rotate the mesh
        """
        return self.rotate([0., 0., thetaz])

    def rotate(self, angles):
        """Rotates the mesh in 3D giving the 3 rotation angles that are defined around fixed axes.

        Parameters
        ----------
        angles : array_like
            The 3 angles of the 3D rotation (rad)

        Returns
        -------
        ndarray
            The (3x3) rotation matrix that has been applied to rotate the mesh
        """
        if self.has_surface_integrals():
            self._remove_surface_integrals()
        # TODO: docstring
        # FIXME : code en doublon par rapport a la fonction _rodrigues du module geometry
        
        angles = np.asarray(angles, dtype=np.float)
        theta = np.linalg.norm(angles)
        if theta == 0.:
            return np.eye(3)
        
        ctheta = math.cos(theta)
        stheta = math.sin(theta)

        nx, ny, nz = angles/theta
        nxny = nx*ny
        nxnz = nx*nz
        nynz = ny*nz
        nx2 = nx*nx
        ny2 = ny*ny
        nz2 = nz*nz

        rot_matrix = ctheta*np.eye(3) \
            + (1-ctheta) * np.array([[nx2, nxny, nxnz],
                                     [nxny, ny2, nynz],
                                     [nxnz, nynz, nz2]]) \
            + stheta * np.array([[0., -nz, ny],
                                [nz, 0., -nx],
                                [-ny, nx, 0.]])
        
        # TODO: travailler avec une classe rotation
        self._vertices = np.transpose(np.dot(rot_matrix, self._vertices.copy().T))

        # Updating faces properties if any
        # TODO: use traitlets...
        if self._has_faces_properties():
            # Rotating normals and centers too
            normals = self.__internals__['faces_normals']
            centers = self.__internals__['faces_centers']
            self.__internals__['faces_normals'] = np.transpose(np.dot(rot_matrix, normals.T))
            self.__internals__['faces_centers'] = np.transpose(np.dot(rot_matrix, centers.T))
            
        if self.has_surface_integrals():
            self._remove_surface_integrals()
            
        return rot_matrix

    def translate_x(self, tx):
        """Translates the mesh along the Ox axis.
        
        Parameters
        ----------
        tx : float
            Distance
        """
        vertices = self._vertices
        vertices[:, 0] += tx
        self._vertices = vertices

        # Updating properties if any
        if self._has_faces_properties():
            centers = self.__internals__['faces_centers']
            centers[:, 0] += tx
            self.__internals__['faces_centers'] = centers
            
        if self.has_surface_integrals():
            self._remove_surface_integrals()
            
        return

    def translate_y(self, ty):
        """Translates the mesh along the Oy axis.

        Parameters
        ----------
        ty : float
            Distance
        """
        vertices = self._vertices.copy()
        vertices[:, 1] += ty
        self._vertices = vertices

        # Updating properties if any
        if self._has_faces_properties():
            centers = self.__internals__['faces_centers']
            centers[:, 1] += ty
            self.__internals__['faces_centers'] = centers
            
        if self.has_surface_integrals():
            self._remove_surface_integrals()
            
        return

    def translate_z(self, tz):
        """Translates the mesh along the Oz axis.

        Parameters
        ----------
        tz : float
            Distance
        """
        vertices = self._vertices.copy()
        vertices[:, 2] += tz
        self._vertices = vertices

        # Updating properties if any
        if self._has_faces_properties():
            centers = self.__internals__['faces_centers']
            centers[:, 2] += tz
            self.__internals__['faces_centers'] = centers
            
        if self.has_surface_integrals():
            self._remove_surface_integrals()
            
        return

    def translate(self, t):
        """Translates the mesh in 3D giving the 3 distances along coordinate axes.
        
        Parameters
        ----------
        t : array_like
            translation vector
        """
        tx, ty, tz = t
        V = self.vertices.copy() # FIXME: why doing a copy ???
        V[:, 0] += tx
        V[:, 1] += ty
        V[:, 2] += tz
        self.vertices = V

        # Updating properties if any
        if self._has_faces_properties():
            centers = self.__internals__['faces_centers']
            centers[:, 0] += tx
            centers[:, 1] += ty
            centers[:, 2] += tz
            self.__internals__['faces_centers'] = centers
        
        if self.has_surface_integrals():
            self._remove_surface_integrals()
            
        return

    def scale(self, alpha):
        """Scales the mesh.
        
        Parameters
        ----------
        alpha : float
            A positive scaling factor
        """
        assert 0 < alpha
        
        # TODO: voir pourquoi il est fait une copie ici...
        vertices = self._vertices.copy()
        vertices *= float(alpha)
        self._vertices = vertices

        if self._has_faces_properties():
            self._remove_faces_properties()
            
        return

    def scalex(self, alpha):
        """Scales the mesh along the x axis.
        
        Parameters
        ----------
        alpha : float
            A positive scaling factor
        """
        assert 0 < alpha
        
        vertices = self._vertices.copy()
        vertices[:, 0] *= float(alpha)
        self._vertices = vertices

        if self._has_faces_properties():
            self._remove_faces_properties()

        return

    def scaley(self, alpha):
        """Scales the mesh along the y axis.

        Parameters
        ----------
        alpha : float
            A positive scaling factor
        """
        assert 0 < alpha
        
        vertices = self._vertices.copy()
        vertices[:, 1] *= float(alpha)
        self._vertices = vertices

        if self._has_faces_properties():
            self._remove_faces_properties()

        return

    def scalez(self, alpha):
        """Scales the mesh along the z axis.

        Parameters
        ----------
        alpha : float
            A positive scaling factor
        """
        assert 0 < alpha
        
        vertices = self._vertices.copy()
        vertices[:, 2] *= float(alpha)
        self._vertices = vertices

        if self._has_faces_properties():
            self._remove_faces_properties()

        return

    def flip_normals(self):
        """Flips every normals of the mesh."""
        
        faces = self._faces.copy()
        self._faces = np.fliplr(faces)

        if self._has_faces_properties():
            self.__internals__['faces_normals'] *= -1
        
        if self.has_surface_integrals():
            self._remove_surface_integrals()

        return

    def __add__(self, mesh_to_add):
        """Adds two meshes
        
        Parameters
        ----------
        mesh_to_add : Mesh
            The other mesh instance to add to the current instance

        Returns
        -------
        Mesh
            The composite mesh
            
        Note
        ----
        This method should not be called as is but it overides the + binary operator for convenience.
        """
        
        assert isinstance(mesh_to_add, Mesh)
        vertices = np.concatenate((self._vertices, mesh_to_add._vertices), axis=0)
        faces = np.concatenate((self._faces, mesh_to_add._faces + self.nb_vertices), axis=0)
        new_mesh = Mesh(vertices, faces, name='_'.join([self.name, mesh_to_add.name]))
        new_mesh.merge_duplicates()
        new_mesh._verbose = self._verbose or mesh_to_add._verbose

        return new_mesh

    def copy(self, name=None):
        """Get a copy of the current mesh instance.

        Parameters
        ----------
        name : string, optional
            a new name for the new mesh
        
        Returns
        -------
        Mesh
            mesh instance copy
        """
        new_mesh = copy.deepcopy(self)
        if name is not None:
            new_mesh.name = name
        return new_mesh

    def merge_duplicates(self, atol=1e-8, return_index=False):
        """Merges the duplicate vertices of the mesh.
        
        Parameters
        ----------
        atol : float, optional
            Absolute tolerance. default is 1e-8
        return_index : bool, optional
            Flag to return

        Returns
        -------
        new_id : ndarray, optional
            Array of indices that merges the vertices. Returned if return_index = True
            
        See Also
        --------
        meshmagick.tools.merge_duplicate_rows
        
        """
        uniq, new_id = merge_duplicate_rows(self._vertices, atol=atol, return_index=True)

        nv_init = self.nb_vertices

        # Updating mesh data
        self._vertices = uniq
        self._faces = new_id[self._faces] # Faces vertices ids are updated here

        nv_final = self.nb_vertices

        if self._verbose:
            print("* Merging duplicate vertices that lie in an absolute proximity of %.1E..." % atol)
            delta_n = nv_init - nv_final
            if delta_n == 0:
                print("\t--> No duplicate vertices have been found")
            else:
                print("\t--> Initial number of vertices : %u" % nv_init)
                print("\t--> Final number of vertices   : %u" % nv_final)
                print("\t--> %u vertices have been merged\n" % delta_n)

        if self._has_connectivity():
            self._remove_connectivity()

        if return_index:
            return new_id
        else:
            return

    def heal_normals(self):
        """Heals the mesh's normals orientations so that they have a consistent orientation and try to make them outward.
        """
        # TODO: return the different groups of a mesh in case it is made of several unrelated groups

        nv = self.nb_vertices
        nf = self.nb_faces
        faces = self._faces

        # Building connectivities
        v_v = self.vv
        v_f = self.vf
        f_f = self.ff
        boundaries = self.boundaries

        if len(boundaries) > 0:
            mesh_closed = False
        else:
            mesh_closed = True

        # Flooding the mesh to find inconsistent normals
        type_cell = np.zeros(nf, dtype=np.int32)
        type_cell[:] = 4
        type_cell[self.triangles_ids] = 3

        f_vis = np.zeros(nf, dtype=bool)
        f_vis[0] = True
        stack = [0]
        nb_reversed = 0
        while 1:
            if len(stack) == 0:
                if np.any(np.logical_not(f_vis)):
                    iface = np.where(np.logical_not(f_vis))[0][0]
                    stack.append(iface)
                    f_vis[iface] = True
                else:
                    break

            iface = stack.pop()
            face = faces[iface]
            s1 = set(face)

            for iadj_f in f_f[iface]:
                if f_vis[iadj_f]:
                    continue
                f_vis[iadj_f] = True
                # Removing the other pointer
                f_f[iadj_f].remove(iface)  # So as it won't go from iadj_f to iface in the future

                # Shared vertices
                adjface = faces[iadj_f]
                s2 = set(adjface)
                # try:
                common_vertices = list(s1 & s2)
                if len(common_vertices) == 2:
                    i_v1, i_v2 = common_vertices
                else:
                    print('WARNING: faces %u and %u have more than 2 vertices in common !' % (iface, iadj_f))
                    continue

                # Checking normal consistency
                face_ref = np.roll(face[:type_cell[iface]], -np.where(face == i_v1)[0][0])
                adj_face_ref = np.roll(adjface[:type_cell[iadj_f]], -np.where(adjface == i_v1)[0][0])

                if face_ref[1] == i_v2:
                    i = 1
                else:
                    i = -1

                if adj_face_ref[i] == i_v2:
                    # Reversing normal
                    nb_reversed += 1
                    faces[iadj_f] = np.flipud(faces[iadj_f])

                # Appending to the stack
                stack.append(iadj_f)

        if self._verbose:
            print("* Healing normals to make them consistent and if possible outward")
            if nb_reversed > 0:
                print('\t--> %u faces have been reversed to make normals consistent across the mesh' % (nb_reversed))
            else:
                print("\t--> Normals orientations are consistent")

        self._faces = faces

        # Checking if the normals are outward
        if mesh_closed:
            zmax = np.max(self._vertices[:, 2])

            areas = self.faces_areas
            normals = self.faces_normals
            centers = self.faces_centers
            # areas, normals, centers = get_all_faces_properties(vertices, faces)

            hs = (np.array([(centers[:, 2] - zmax) * areas, ] * 3).T * normals).sum(axis=0)

            tol = 1e-9
            if math.fabs(hs[0]) > tol or math.fabs(hs[1]) > tol:
                if self._verbose:
                    print("\t--> WARNING: the mesh does not seem watertight althought marked as closed...")

            if hs[2] < 0:
                flipped = True
                self.flip_normals()
            else:
                flipped = False

            if self._verbose and flipped:
                print('\t--> Every normals have been reversed to be outward')


        else:
            if self._verbose:
                print("\t--> Mesh is not closed, meshmagick cannot test if the normals are outward")

        if self._has_faces_properties():
            self._remove_faces_properties()

        return

    def remove_unused_vertices(self):
        """Removes unused vertices in the mesh.
        
        Those are vertices that are not used by any face connectivity.
        """
        # TODO: implementer return_index !!
        nv = self.nb_vertices
        vertices, faces = self._vertices, self._faces

        used_v = np.zeros(nv, dtype=np.bool)
        used_v[sum(list(map(list, faces)), [])] = True
        nb_used_v = sum(used_v)

        if nb_used_v < nv:
            new_id__v = np.arange(nv)
            new_id__v[used_v] = np.arange(nb_used_v)
            faces = new_id__v[faces]
            vertices = vertices[used_v]

        self._vertices, self._faces = vertices, faces

        if self._verbose:
            print("* Removing unused vertices in the mesh:")
            if nb_used_v < nv:
                unused_v = np.where(np.logical_not(used_v))[0]
                vlist_str = '[' + ', '.join(str(iV) for iV in unused_v) + ']'
                print("\t--> %u unused vertices have been removed" % (nv - nb_used_v))
            else:
                print("\t--> No unused vertices")

        if self._has_connectivity():
            self._remove_connectivity()

        return

    def heal_triangles(self):
        """Makes the triangle connectivity consistent.
        
        A general face is stored internally as a 4 integer array. It allows to describe indices of a quadrangle's vertices. For triangles, the first index should be equal to the last. This method ensures that this rule is applied everywhere and correct bad triangles description.
        """
        if self._has_faces_properties():
            self._remove_faces_properties()
        
        faces = self._faces

        quads = faces[:, 0] != faces[:, -1]
        nquads_init = sum(quads)

        faces[quads] = np.roll(faces[quads], 1, axis=1)
        quads = faces[:, 0] != faces[:, -1]

        faces[quads] = np.roll(faces[quads], 1, axis=1)
        quads = faces[:, 0] != faces[:, -1]

        faces[quads] = np.roll(faces[quads], 1, axis=1)
        quads = faces[:, 0] != faces[:, -1]
        nquads_final = sum(quads)

        self._faces = faces

        if self._verbose:
            print("* Ensuring consistent definition of triangles:")
            if nquads_final < nquads_init:
                print("\t--> %u triangles were described the wrong way and have been corrected" % (
                nquads_init - nquads_final))
            else:
                print("\t--> Triangle description is consistent")

        return

    def remove_degenerated_faces(self, rtol=1e-5):
        """Removes tiny triangles from the mesh.
        
        Tiny triangles are those whose area is lower than the mean triangle area in the mesh times the relative
        tolerance given.
        
        Parameters
        ----------
        rtol : float, optional
            Positive relative tolerance
        """
        
        assert 0 < rtol
        
        # TODO: implementer un retour d'index des faces extraites
        areas = self.faces_areas
        area_threshold = areas.mean() * float(rtol)

        # Detecting faces that have null area
        faces = self._faces[np.logical_not(areas < area_threshold)]
        if self._verbose:
            nb_removed = self.nb_faces - faces.shape[0]
            print('* Removing degenerated faces')
            if nb_removed > 0:
                print('\t-->%u degenerated faces have been removed' % nb_removed)
            else:
                print('\t--> No degenerated faces')

        self._faces = faces
        
        if self._has_faces_properties():
            self._remove_faces_properties()
            
        return

    def heal_mesh(self):
        """Heals the mesh for different tests available.
        
        It applies:
        
        * Unused vertices removal
        * Degenerate faces removal
        * Duplicate vertices merging
        * Triangles healing
        * Normal healing
        """
        if self._has_faces_properties():
            self._remove_faces_properties()
        self.remove_unused_vertices()
        self.remove_degenerated_faces()
        self.merge_duplicates()
        self.heal_triangles()
        self.heal_normals()
        return

    def triangulate_quadrangles(self):
        """Triangulates every quadrangles of the mesh by simple spliting.
        
        Each quadrangle gives two triangles.
        
        Note
        ----
        No checking is made on the triangle quality is done.
        """
        # TODO: Ensure the best quality aspect ratio of generated triangles
        
        # Defining both triangles id lists to be generated from quadrangles
        t1 = (0, 1, 2)
        t2 = (0, 2, 3)

        faces = self._faces

        # Triangulation
        new_faces = faces[self.quadrangles_ids].copy()
        new_faces[:, :3] = new_faces[:, t1]
        new_faces[:, -1] = new_faces[:, 0]

        faces[self.quadrangles_ids, :3] = faces[:, t2][self.quadrangles_ids]
        faces[self.quadrangles_ids, -1] = faces[self.quadrangles_ids, 0]

        faces = np.concatenate((faces, new_faces))

        if self._verbose:
            print('\nTriangulating quadrangles')
            if self.nb_quadrangles != 0:
                print('\t-->{:d} quadrangles have been split in triangles'.format(self.nb_quadrangles))

        self.__internals__.clear()

        self._faces = faces

        return faces

    def symmetrize(self, plane):
        """Symmetrize the mesh with respect to a plane.
        
        Parameters
        ----------
        plane : Plane
            The plane of symmetry
        """
        # Symmetrizing the nodes
        vertices, faces = self._vertices, self._faces

        vertices = np.concatenate((vertices, vertices - 2 * np.outer(np.dot(vertices, plane.normal) - plane.c, plane.normal)))
        faces = np.concatenate((faces, np.fliplr(faces.copy() + self.nb_vertices)))

        self._vertices, self._faces = vertices, faces
        verbose = self.verbose
        self.verbose_off()
        self.merge_duplicates()
        self.verbose = verbose

        self.__internals__.clear()
            
        return
    
    def mirror(self, plane):
        """Mirrors the mesh instance with respect to a plane.
        
        Parameters
        ----------
        plane : Plane
            The mirroring plane
        """
        self._vertices -= 2 * np.outer(np.dot(self._vertices, plane.normal) - plane.c, plane.normal)
        self.flip_normals()
        self.__internals__.clear()
        return
    
    def _compute_faces_integrals(self, sum_faces_contrib=False): # TODO: implementer le sum_surface_contrib

        # TODO: Utiliser sum_faces_contrib
        surface_integrals = np.zeros((15, self.nb_faces), dtype=np.float)

        # First triangles
        if self.nb_triangles > 0:
            triangles_ids = self.triangles_ids
            # print self._faces[triangles_ids][:, :3].shape
            triangles_vertices = self._vertices[self._faces[triangles_ids][:, :3]] # Remettre le 3
            surface_integrals[:, triangles_ids] = self._compute_triangles_integrals(triangles_vertices)

        # Now quadrangles by splitting them up
        if self.nb_quadrangles > 0:
            quadrangles_ids = self.quadrangles_ids
            quadrangles = self._faces[quadrangles_ids]

            # First pass
            surface_integrals[:, quadrangles_ids] = \
                self._compute_triangles_integrals(self._vertices[quadrangles[:, (0, 1, 2)]])

            # Second pass
            surface_integrals[:, quadrangles_ids] += \
                self._compute_triangles_integrals(self._vertices[quadrangles[:, (0, 2, 3)]])

        self.__internals__['surface_integrals'] = surface_integrals

        return
    
    def _remove_surface_integrals(self):
        if 'surface_integrals' in self.__internals__:
            del self.__internals__['surface_integrals']
        return
    
    def has_surface_integrals(self):
        return 'surface_integrals' in self.__internals__

    def get_surface_integrals(self):
        """Get the mesh surface integrals
        
        Returns
        -------
        ndarray
            The mesh surface inegrals array
        """
        # TODO: add an option to do the summation
        # TODO: decrire les integrales de surface en question
        if not self.has_surface_integrals():
            self._compute_faces_integrals()
        return self.__internals__['surface_integrals']

    def _compute_volume(self):
        if not self.has_surface_integrals():
            self._compute_faces_integrals()

        normals = self.faces_normals
        sigma_0_2 = self.__internals__['surface_integrals'][:3]

        return (normals.T * sigma_0_2).sum() / 3.

    @property
    def volume(self):
        """Get the mesh enclosed volume
        
        Returns
        -------
        float
            The mesh volume
        """
        return self._compute_volume()
    
    # TODO: add the possibility to compute the inertia to an other point than [0, 0, 0]
    def eval_plain_mesh_inertias(self, rho_medium=1023.):
        """Evaluates the mesh inertia under the assumption of an enclosed volume made of an homogeneous medium of the given density.
        
        Parameters
        ----------
        rho_medium : float, optional
            The medium density (kg/m**3). Default is 1023 kg.m**3 (salt water)

        Returns
        -------
        RigidBodyInertia
            The mesh inertia instance expressed at origin (0, 0, 0)
        """
        # TODO: allow to specify an other point for inertia matrix expression
        # TODO: manipuler plutot un objet inertia --> creer une classe !
        rho_medium = float(rho_medium)
        
        volume = self.volume
        mass = rho_medium * volume
        
        integrals = self.get_surface_integrals()[6:15]
        sigma_6_8 = integrals[:3]
        
        normals = self.faces_normals.T
        
        cog = (normals * sigma_6_8).sum(axis=1) / (2*volume)
        
        sigma9, sigma10, sigma11 = (normals * integrals[3:6]).sum(axis=1)
        sigma12, sigma13, sigma14 = (normals * integrals[6:10]).sum(axis=1)

        xx = rho_medium * (sigma10 + sigma11) / 3.
        yy = rho_medium * (sigma9 + sigma11) / 3.
        zz = rho_medium * (sigma9 + sigma10) / 3.
        xy = rho_medium * sigma12 / 2.
        xz = rho_medium * sigma14 / 2.
        yz = rho_medium * sigma13 / 2.

        return RigidBodyInertia(mass, cog, xx, yy, zz, yz, xz, xy, point=[0, 0, 0])
    
    def eval_shell_mesh_inertias(self, rho_medium=7850., thickness=0.02):
        """Evaluates the mesh inertia under the assumption of an enclosed volume made of an homogeneous medium of the
        given density.

        Parameters
        ----------
        rho_medium : float, optional
            The medium density (kg/m**3). Default is 7850 kg/m**3 (Steel density)
        thickness : flaot, optional
            The hull thickness (m). Default is 0.02 m.

        Returns
        -------
        RigidBodyInertia
            The mesh inertia instance expressed at origin (0, 0, 0)
        """
        rho_medium = float(rho_medium)
        thickness = float(thickness)
        surf_density = rho_medium * thickness
        
        surface = self.faces_areas.sum()
        mass = surf_density * surface

        s0, s1, s2, s3, s4, s5, s6, s7, s8 = self.get_surface_integrals()[:9].sum(axis=1)
        
        cog = np.array([s0, s1, s2], dtype=np.float) / mass
        
        xx = surf_density * (s7 + s8)
        yy = surf_density * (s6 + s8)
        zz = surf_density * (s6 + s7)
        yz = surf_density * s3
        xz = surf_density * s4
        xy = surf_density * s5
        
        return RigidBodyInertia(mass, cog, xx, yy, zz, yz, xz, xy, point=[0, 0, 0])
        
    def _edges_stats(self):
        """Computes the min, max, and mean of the mesh's edge length"""
        vertices = self.vertices[self.faces]
        edge_length = np.zeros((self.nb_faces, 4), dtype=np.float)
        for i in range(4):
            edge = vertices[:, i, :] - vertices[:, i-1, :]
            edge_length[:, i] = np.sqrt(np.einsum('ij, ij -> i', edge, edge))
            
        return edge_length.min(), edge_length.max(), edge_length.mean()
    
    @property
    def min_edge_length(self):
        """The mesh's minimum edge length"""
        return self._edges_stats()[0]
    
    @property
    def max_edge_length(self):
        """The mesh's maximum edge length"""
        return self._edges_stats()[1]
    
    @property
    def mean_edge_length(self):
        """The mesh's mean edge length"""
        return self._edges_stats()[2]
    
    @staticmethod
    def _compute_triangles_integrals(triangles_vertices, sum_faces_contrib=False):
        """Performs the computation of the various interesting surface integrals.
        
        Notes
        -----
        triangles_vertices doit decrire par dimension croissante du general au particulier :
        dimension 0 : informations sur chaque facette -- triangles_vertices[0] -> facette 0)
        dimension 1 : informations sur chaque vertex de la facette -- triangles_vertices[0, 1] -> vertex 1 de la facette 0
        dimension 2 : information sur chacune des coordonnées des vertex -- triangles_vertices[0, 1, 2] -> coordonnee z du vertex 1 de la facette 0
        
        Todo
        ----
        Explicit the integrals
        """

        s_int = np.zeros((15, triangles_vertices.shape[0]), dtype=np.float)

        point_0, point_1, point_2 = list(map(_3DPointsArray, np.rollaxis(triangles_vertices, 1, 0)))

        t0 = point_0 + point_1
        f1 = t0 + point_2
        t1 = point_0 * point_0
        t2 = t1 + point_1*t0
        f2 = t2 + point_2*f1
        f3 = point_0*t1 + point_1*t2 + point_2*f2
        g0 = f2 + point_0 * (f1 + point_0)
        g1 = f2 + point_1 * (f1 + point_1)
        g2 = f2 + point_2 * (f1 + point_2)

        e1 = point_1 - point_0
        e2 = point_2 - point_0

        delta = np.linalg.norm(np.cross(e1, e2), axis=1)

        s_int[0:3] = np.einsum('i, ij -> ji', delta, f1) / 6.

        s_int[3] = delta * (6.*point_0.y*point_0.z + 3*(point_1.y*point_1.z + point_2.y*point_2.z) - point_0.y*f1[:, 2] - point_0.z*f1[:, 1]) / 12.
        s_int[4] = delta * (6.*point_0.x*point_0.z + 3*(point_1.x*point_1.z + point_2.x*point_2.z) - point_0.x*f1[:, 2] - point_0.z*f1[:, 0]) / 12.
        s_int[5] = delta * (6.*point_0.x*point_0.y + 3*(point_1.x*point_1.y + point_2.x*point_2.y) - point_0.x*f1[:, 1] - point_0.y*f1[:, 0]) / 12.

        s_int[6:9] = np.einsum('i, ij -> ji', delta, f2) / 12.
        s_int[9:12] = np.einsum('i, ij -> ji', delta, f3) / 20.

        s_int[12] = delta * (point_0.y*g0[:, 0] + point_1.y*g1[:, 0] + point_2.y*g2[:, 0]) / 60.
        s_int[13] = delta * (point_0.z*g0[:, 1] + point_1.z*g1[:, 1] + point_2.z*g2[:, 1]) / 60.
        s_int[14] = delta * (point_0.x*g0[:, 2] + point_1.x*g1[:, 2] + point_2.x*g2[:, 2]) / 60.

        return s_int

    def quick_save(self, filename=None):
        """Saves the current mesh instance in a VTK file.
        
        It is mainly for debugging purpose.
        
        Parameters
        ----------
        filename : str
            If None, the file is automatically saved under the name quick_save.vtp.
            If the name given does not have a .vtp extension, the latter is appended automatically.
        """
        if not filename:
            filename = 'quick_save.vtp'
        
        if not filename.endswith('.vtp'):
            filename += '.vtp'
        try:
            from .mmio import write_VTP
            write_VTP(filename, self.vertices, self.faces)
            print('File %s written' % filename)
        except ImportError:
            raise ImportError('mmio module not found')


class _3DPointsArray(np.ndarray):
    def __new__(cls, points):
        obj = np.asarray(points).view(cls)
        cls.x = property(fget=lambda cls: cls[:, 0])
        cls.y = property(fget=lambda cls: cls[:, 1])
        cls.z = property(fget=lambda cls: cls[:, 2])
        return obj
