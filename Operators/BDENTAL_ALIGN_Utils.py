import time, os, sys, shutil, math, threading, platform, subprocess, string
from math import degrees, radians, pi, ceil, floor
import numpy as np
from time import sleep, perf_counter as Tcounter
from queue import Queue

path = R"C:\MyPythonResources\Requirements"
sys.path.append(path)

import SimpleITK as sitk
import cv2
import vtk
from vtk.util import numpy_support
from vtk import vtkCommand

# Blender Imports :
import bpy
import bmesh
from mathutils import Matrix, Vector, Euler, kdtree

# Global Variables :
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ProgEvent = vtkCommand.ProgressEvent

#######################################################################################
# Popup message box function :
#######################################################################################


# Popup message box function :
def ShowMessageBox(message=[], title="INFO", icon="INFO"):
    def draw(self, context):
        for txtLine in message:
            self.layout.label(text=txtLine)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


def ShowMessageBox2(message=[], title="INFO", icon="INFO"):
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        for txtLine in message:
            row = box.row()
            row.label(text=txtLine)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


###########################################################################
# Functions :
###########################################################################
def MoveToCollection(obj, CollName):

    OldColl = obj.users_collection  # list of all collection the obj is in
    NewColl = bpy.data.collections.get(CollName)
    if not NewColl:
        NewColl = bpy.data.collections.new(CollName)
        bpy.context.scene.collection.children.link(NewColl)
    if not obj in NewColl.objects[:]:
        NewColl.objects.link(obj)  # link obj to scene
    if OldColl:
        for Coll in OldColl:  # unlink from all  precedent obj collections
            if Coll is not NewColl:
                Coll.objects.unlink(obj)


def AddRefPoint(name, color, CollName=None):

    loc = bpy.context.scene.cursor.location
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.2, location=loc)
    RefP = bpy.context.object
    RefP.name = name
    RefP.data.name = name + "_mesh"
    if CollName:
        MoveToCollection(RefP, CollName)
    if name.startswith("B"):
        matName = "TargetRefMat"
    if name.startswith("M"):
        matName = "SourceRefMat"

    mat = bpy.data.materials.get(matName) or bpy.data.materials.new(matName)
    mat.diffuse_color = color
    mat.use_nodes = True
    RefP.active_material = mat
    RefP.show_name = True
    return RefP


def RefPointsToTransformMatrix(TargetRefPoints, SourceRefPoints):
    # TransformMatrix = Matrix()  # identity Matrix (4x4)

    # make 2 arrays of coordinates :
    TargetArray = np.array(
        [obj.location for obj in TargetRefPoints], dtype=np.float64
    ).T
    SourceArray = np.array(
        [obj.location for obj in SourceRefPoints], dtype=np.float64
    ).T

    # Calculate centers of Target and Source RefPoints :
    TargetCenter, SourceCenter = np.mean(TargetArray, axis=1), np.mean(
        SourceArray, axis=1
    )

    # Calculate Translation :
    ###################################

    # TransMatrix_1 : Matrix(4x4) will translate center of SourceRefPoints...
    # to origine (0,0,0) location.
    TransMatrix_1 = Matrix.Translation(Vector(-SourceCenter))

    # TransMatrix_2 : Matrix(4x4) will translate center of SourceRefPoints...
    #  to the center of TargetRefPoints location.
    TransMatrix_2 = Matrix.Translation(Vector(TargetCenter))

    # Calculate Rotation :
    ###################################

    # Home Arrays will get the Centered Target and Source RefPoints around origin (0,0,0).
    HomeTargetArray, HomeSourceArray = (
        TargetArray - TargetCenter.reshape(3, 1),
        SourceArray - SourceCenter.reshape(3, 1),
    )
    # Rigid transformation via SVD of covariance matrix :
    U, S, Vt = np.linalg.svd(np.dot(HomeTargetArray, HomeSourceArray.T))

    # rotation matrix from SVD orthonormal bases :
    R = np.dot(U, Vt)
    if np.linalg.det(R) < 0.0:
        Vt[2, :] *= -1
        R = np.dot(U, Vt)
        print(" Reflection fixed ")

    RotationMatrix = Matrix(R).to_4x4()
    TransformMatrix = TransMatrix_2 @ RotationMatrix @ TransMatrix_1

    return TransformMatrix


##############################################################
# Align utils :
##############################################################
# Copyright (c) 2005, Chris Want
"""
VTK inside Blender module.
Please see LICENSE and README.md for information about this software.
"""


class BlenderToPolyData:
    ### Below is the public interface of this class

    def __init__(self, obj, uvlayer=None):
        self.obj = obj
        self.mesh = obj.data
        self.points = vtk.vtkPoints()
        self.polys = vtk.vtkCellArray()
        self.lines = vtk.vtkCellArray()
        self.pdata = vtk.vtkPolyData()

    def convert_data(self):
        self.create_point_data()
        self.process_faces()
        self.process_edges()
        self.create_pdata()
        # self.process_uvcoords()
        # self.pdata.Update()
        return self.pdata

    @classmethod
    def convert(cls, obj, uvlayer=None):
        ob = cls(obj, uvlayer)
        return ob.convert_data()

    ## Below should be regarded 'private' ...
    def create_pdata(self):
        self.pdata.SetPoints(self.points)
        self.pdata.SetPolys(self.polys)
        self.pdata.SetLines(self.lines)

    def create_point_data(self):
        pcoords = vtk.vtkFloatArray()
        pcoords.SetNumberOfComponents(3)
        pcoords.SetNumberOfTuples(len(self.mesh.vertices))
        for i in range(len(self.mesh.vertices)):
            v = self.mesh.vertices[i]
            p0 = obj.matrix_world @ v.co[0]
            p1 = obj.matrix_world @ v.co[1]
            p2 = obj.matrix_world @ v.co[2]
            pcoords.SetTuple3(i, p0, p1, p2)

        self.points.SetData(pcoords)

    def process_faces(self):
        for face in self.mesh.polygons:
            self.polys.InsertNextCell(len(face.vertices))
            for i in range(len(face.vertices)):
                self.polys.InsertCellPoint(face.vertices[i])

    def process_edges(self):
        for edge in self.mesh.edges:
            self.lines.InsertNextCell(len(edge.vertices))
            for i in range(len(edge.vertices)):
                self.lines.InsertCellPoint(edge.vertices[i])

    def process_uvcoords(self):
        if me.faceUV:
            if uvlayer:
                uvnames = me.getUVLayerNames()
                if uvlayer in uvnames:
                    me.activeUVLayer = uvlayer
                    tcoords = vtk.vtkFloatArray()
                    tcoords.SetNumberOfComponents(2)
                    tcoords.SetNumberOfTuples(len(me.verts))
                    for face in me.faces:
                        for i in range(len(face.verts)):
                            uv = face.uv[i]
                            tcoords.SetTuple2(face.v[i].index, uv[0], uv[1])
                            pdata.GetPointData().SetTCoords(tcoords)


class PolyDataMapperToBlender:
    # some flags to alter behavior
    TRIS_TO_QUADS = 0x01
    SMOOTH_FACES = 0x02

    ### Below is the public interface for this class
    def __init__(self, pmapper, me=None):
        self.initialize_work_data()
        self.initialize_mesh(me)
        self.pmapper = pmapper

    def convert_data(self):
        self.initialize_work_data()
        self.pmapper.Update()

        pdata = self.pmapper.GetInput()
        plut = self.pmapper.GetLookupTable()
        scalars = pdata.GetPointData().GetScalars()

        # print(pdata.GetNumberOfCells())

        self.point_data_to_verts(pdata)
        self.read_colors(scalars, plut)
        self.process_topology(pdata, scalars)

        self.mesh.from_pydata(self.verts, self.edges, self.faces)

        self.set_smooth()
        self.apply_vertex_colors()
        # self.set_materials()
        if not self.newmesh:
            self.mesh.update()

        return self.mesh

    @classmethod
    def convert(cls, pmapper, me=None):
        ob = cls(pmapper, me)
        return ob.convert_data()

    # What is this 'tri to quad' stuff? Well, sometimes it's best to
    # try to read in pairs of consecutive triangles in as quad faces.
    # An example: you extrude a tube along a polyline in vtk, and if
    # you can get it into Blender as a bunch of quads, you can use a
    # Catmull-Clark subdivision surface to smooth the tube out, with
    # fewer creases.

    def set_tris_to_quads(self):
        self.flags = flags | self.TRIS_TO_QUADS

    def set_tris_to_tris(self):
        self.flags = flags & ~self.TRIS_TO_QUADS

    def set_faces_to_smooth(self):
        self.flags = flags | self.SMOOTH_FACES

    def set_faces_to_faceted(self):
        self.flags = flags & ~self.SMOOTH_FACES

    ### Below should be considered private to this class

    def initialize_work_data(self):
        self.verts = []
        self.faces = []
        self.edges = []
        self.oldmats = None
        self.colors = None
        self.flags = 0

    def initialize_mesh(self, me=None):
        self.newmesh = False
        if me == None:
            self.mesh = bpy.data.meshes.new("VTKBlender")
            self.newmesh = True
        else:
            self.mesh = me
            self.remove_mesh_data()
            if me.materials:
                self.oldmats = me.materials

    def remove_mesh_data(self):
        bm = bmesh.new()
        bm.from_mesh(self.mesh)
        all_verts = [v for v in bm.verts]
        DEL_VERTS = 1
        bmesh.ops.delete(bm, geom=all_verts, context=DEL_VERTS)
        bm.to_mesh(self.mesh)

    def point_data_to_verts(self, pdata):
        self.verts = []
        for i in range(pdata.GetNumberOfPoints()):
            point = pdata.GetPoint(i)
            self.add_vert(point[0], point[1], point[2])

    def add_vert(self, x, y, z):
        self.verts.append([x, y, z])

    def read_colors(self, scalars, plut):
        if (scalars != None) and (plut != None):
            self.colors = []

            scolor = [0, 0, 0]
            for i in range(scalars.GetNumberOfTuples()):
                plut.GetColor(scalars.GetTuple1(i), scolor)

                color = scolor
                alpha = plut.GetOpacity(scalars.GetTuple1(i))
                self.colors.append([scolor[0], scolor[1], scolor[2], alpha])

    def set_smooth(self):
        if self.flags & self.SMOOTH_FACES:
            for f in me.faces:
                f.smooth = 1

    def apply_vertex_colors(self):
        # Some faces in me.faces may have been discarded from our
        # list, so best to compute the vertex colors after the faces
        # have been added to the mesh
        if self.colors != None:
            if not self.mesh.vertex_colors:
                self.mesh.vertex_colors.new()
            color_layer = self.mesh.vertex_colors.active
            i = 0
            for poly in self.mesh.polygons:
                for idx in poly.vertices:
                    rgb = self.colors[idx]
                    # No alpha? Why Blender, why?
                    color_layer.data[i].color = rgb[0:3]
                    i += 1

    def set_materials(self):
        if not self.mesh.materials:
            if self.oldmats:
                self.mesh.materials = oldmats
            else:
                newmat = Material.New()
                if colors != None:
                    newmat.mode |= Material.Modes.VCOL_PAINT
                    self.mesh.materials = [newmat]

    def process_line(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        self.add_edge(n1, n2)

    def process_polyline(self, cell):
        for j in range(cell.GetNumberOfPoints() - 1):
            n1 = cell.GetPointId(j)
            n2 = cell.GetPointId(j + 1)
            self.add_edge(n1, n2)

    def process_triangle(self, cell, skiptriangle):
        if skiptriangle:
            skiptriangle = False
            return

        if (
            (self.flags & self.TRIS_TO_QUADS)
            and (i < pdata.GetNumberOfCells() - 1)
            and (pdata.GetCellType(i + 1) == 5)
        ):
            n1 = cell.GetPointId(0)
            n2 = cell.GetPointId(1)
            n3 = cell.GetPointId(2)
            nextcell = pdata.GetCell(i + 1)
            m1 = nextcell.GetPointId(0)
            m2 = nextcell.GetPointId(1)
            m3 = nextcell.GetPointId(2)
            if (n2 == m3) and (n3 == m2):
                self.add_face(n1, n2, m1, n3)
                skiptriangle = True
            else:
                self.add_face(n1, n2, n3)

        else:
            n1 = cell.GetPointId(0)
            n2 = cell.GetPointId(1)
            n3 = cell.GetPointId(2)

            self.add_face(n1, n2, n3)

    def process_triangle_strip(self, cell):
        numpoints = cell.GetNumberOfPoints()
        if (self.flags & self.TRIS_TO_QUADS) and (numpoints % 2 == 0):
            for j in range(cell.GetNumberOfPoints() - 3):
                if j % 2 == 0:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j + 1)
                    n3 = cell.GetPointId(j + 2)
                    n4 = cell.GetPointId(j + 3)

                    self.add_face(n1, n2, n4, n3)
        else:
            for j in range(cell.GetNumberOfPoints() - 2):
                if j % 2 == 0:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j + 1)
                    n3 = cell.GetPointId(j + 2)
                else:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j + 2)
                    n3 = cell.GetPointId(j + 1)

                self.add_face(n1, n2, n3)

    def process_polygon(self, cell, pdata, scalars):
        # Add a vert at the center of the polygon,
        # and break into triangles
        x = 0.0
        y = 0.0
        z = 0.0
        scal = 0.0
        N = cell.GetNumberOfPoints()
        for j in range(N):
            point = pdata.GetPoint(cell.GetPointId(j))
            x = x + point[0]
            y = y + point[1]
            z = z + point[2]
            if scalars != None:
                scal = scal + scalars.GetTuple1(j)

        x = x / N
        y = y / N
        z = z / N
        scal = scal / N

        newidx = len(self.verts)
        self.add_vert(x, y, z)

        if scalars != None:
            scolor = [0, 0, 0]
            plut.GetColor(scal, scolor)
            color = map(vtk_to_blender_color, scolor)
            alpha = int(plut.GetOpacity(scalars.GetTuple1(i)) * 255)
            colors.append([color[0], color[1], color[2], alpha])

        # Add triangles connecting polynomial sides to new vert
        for j in range(N):
            n1 = cell.GetPointId(j)
            n2 = cell.GetPointId((j + 1) % N)
            n3 = newidx
            self.add_face(n1, n2, n3)

    def process_pixel(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        n3 = cell.GetPointId(2)
        n4 = cell.GetPointId(3)

        self.add_face(n1, n2, n3, n4)

    def process_quad(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        n3 = cell.GetPointId(2)
        n4 = cell.GetPointId(3)

        self.add_face(n1, n2, n3, n4)

    def process_topology(self, pdata, scalars):
        skiptriangle = False

        for i in range(pdata.GetNumberOfCells()):
            cell = pdata.GetCell(i)

            # print(i, pdata.GetCellType(i))

            # Do line
            if pdata.GetCellType(i) == 3:
                self.process_line(cell)

            # Do poly lines
            if pdata.GetCellType(i) == 4:
                self.process_polyline(cell)

            # Do triangles
            if pdata.GetCellType(i) == 5:
                self.process_triangle(cell, skiptriangle)

            # Do triangle strips
            if pdata.GetCellType(i) == 6:
                self.process_triangle_strip(cell)

            # Do polygon
            if pdata.GetCellType(i) == 7:
                self.process_polygon(cell, pdata, scalars)

            # Do pixel
            if pdata.GetCellType(i) == 8:
                self.process_pixel(cell)

            # Do quad
            if pdata.GetCellType(i) == 9:
                self.process_quad(cell)

    def vtk_to_blender_color(self, x):
        return int(255 * float(x) + 0.5)

    def add_face(self, n1, n2, n3, n4=None):
        if n4 != None:
            self.faces.append([n1, n2, n3, n4])
        else:
            self.faces.append([n1, n2, n3])

    def add_edge(self, n1, n2):
        self.edges.append([n1, n2])


def VtkICPTransform(SourceVcoList, TargetVcoList, iterations=20, Precision=0.0000001):
    print("Running ICP")
    SourcePolyData = VcoListToVtkPolyData(VcoList=SourceVcoList)
    TargetPolyData = VcoListToVtkPolyData(VcoList=TargetVcoList)

    icp = vtk.vtkIterativeClosestPointTransform()
    icp.SetSource(SourcePolyData)
    icp.SetTarget(TargetPolyData)
    # icp.DebugOn()
    icp.SetMaximumNumberOfIterations(iterations)
    icp.SetMaximumNumberOfLandmarks(SourcePolyData.GetNumberOfPoints())
    icp.SetCheckMeanDistance(1)
    icp.SetMaximumMeanDistance(Precision)
    icp.StartByMatchingCentroidsOn()
    icp.GetLandmarkTransform().SetModeToRigidBody()

    icp.Modified()
    icp.Update()
    TransformMatrix = Matrix()
    for i in range(4):
        for j in range(4):
            TransformMatrix[i][j] = icp.GetMatrix().GetElement(i, j)

    return TransformMatrix


def IcpPairs(SourceObj, TargetObj, VG=False):
    PairsDict = {}
    Objects = {SourceObj: "Source", TargetObj: "Target"}
    if VG == True:
        for obj, Tag in Objects.items():
            ICP_VGroup = obj.vertex_groups.get("ICP")
            if ICP_VGroup:
                obj.vertex_groups.active = ICP_VGroup
                bpy.ops.object.select_all(action="DESELECT")
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="DESELECT")
                bpy.ops.object.vertex_group_select()
                bpy.ops.object.mode_set(mode="OBJECT")
                verts = obj.data.vertices
                SelectVertsGlobCo = [obj.matrix_world @ v.co for v in verts if v.select]
                VertsCoArray = np.array(SelectVertsGlobCo)
                PairsDict[Tag] = VertsCoArray
            else:
                verts = obj.data.vertices
                VertsGlobCo = [obj.matrix_world @ v.co for v in verts]
                VertsCoArray = np.array(VertsGlobCo)
                PairsDict[Tag] = VertsCoArray

        bpy.ops.object.select_all(action="DESELECT")

    if VG == False:
        for obj, Tag in Objects.items():
            verts = obj.data.vertices
            VertsGlobCo = [obj.matrix_world @ v.co for v in verts]
            VertsCoArray = np.array(VertsGlobCo)
            PairsDict[Tag] = VertsCoArray

    return PairsDict


def VcoListToVtkPolyData(VcoList):

    VtkPoints = vtk.vtkPoints()
    VtkVerts = vtk.vtkCellArray()

    for co in VcoList:
        id = VtkPoints.InsertNextPoint(co)
        VtkVerts.InsertNextCell(1)
        VtkVerts.InsertCellPoint(id)

    VtkPolyData = vtk.vtkPolyData()
    VtkPolyData.SetPoints(VtkPoints)
    VtkPolyData.SetVerts(VtkVerts)

    return VtkPolyData


def KdIcpPairs(SourceVcoList, TargetVcolist, VertsLimite=5000):
    start = Tcounter()
    # print("KD processing start...")
    SourceKdList, TargetKdList, IndexList, DistList = [], [], [], []
    size = len(TargetVcolist)
    kd = kdtree.KDTree(size)

    for i, Vco in enumerate(TargetVcolist):
        kd.insert(Vco, i)

    kd.balance()

    n = len(SourceVcoList)
    if n > VertsLimite:
        step = ceil(n / VertsLimite)
        SourceVcoList = SourceVcoList[::step]

    for Sco in SourceVcoList:

        Tco, index, dist = kd.find(Sco)
        if Tco:
            if not index in IndexList:
                IndexList.append(index)
                TargetKdList.append(Tco)
                SourceKdList.append(Sco)
                DistList.append(dist)
    finish = Tcounter()
    # print(f"KD total iterations : {len(SourceVcoList)}")
    # print(f"KD Index List : {len(IndexList)}")

    # print(f"KD finshed in {finish-start} secondes")
    return SourceKdList, TargetKdList, DistList


def ObjectToIcpVcoList(obj, VG):
    IcpVidDict = VG
    if IcpVidDict:

        SourceVidList, TargetVidList = (
            IcpVidDict[SourceObj],
            IcpVidDict[TargetObj],
        )
        SourceVcoList = [
            SourceObj.matrix_world @ SourceObj.data.vertices[idx].co
            for idx in SourceVidList
        ]
        TargetVcoList = [
            TargetObj.matrix_world @ TargetObj.data.vertices[idx].co
            for idx in TargetVidList
        ]
        ICP_VGroup = obj.vertex_groups.get("BDENTAL_ICP_VG")
        if ICP_VGroup:
            obj.vertex_groups.active = ICP_VGroup
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="DESELECT")
            bpy.ops.object.vertex_group_select()
            bpy.ops.object.mode_set(mode="OBJECT")
            verts = obj.data.vertices
            SelectVertsGlobCo = [obj.matrix_world @ v.co for v in verts if v.select]
            VertsCoList = SelectVertsGlobCo
        else:
            verts = obj.data.vertices
            VertsCoList = [obj.matrix_world @ v.co for v in verts]

    if VG == False:
        verts = obj.data.vertices
        VertsCoList = [obj.matrix_world @ v.co for v in verts]

    # bpy.ops.object.select_all(action="DESELECT")

    return VertsCoList


def KdRadiusVerts(obj, RefCo, radius):
    # start = Tcounter()
    # print("KD processing start...")
    RadiusVertsIds = []
    RadiusVertsCo = []
    RadiusVertsDistance = []
    verts = obj.data.vertices
    Vcolist = [obj.matrix_world @ v.co for v in verts]
    size = len(Vcolist)
    kd = kdtree.KDTree(size)

    for i, Vco in enumerate(Vcolist):
        kd.insert(Vco, i)

    kd.balance()

    for (co, index, dist) in kd.find_range(RefCo, radius):

        RadiusVertsIds.append(index)
        RadiusVertsCo.append(co)
        RadiusVertsDistance.append(dist)

    # finish = Tcounter()
    # print(f"KD radius finshed in {finish-start} secondes")
    return RadiusVertsIds, RadiusVertsCo, RadiusVertsDistance


def VidDictFromPoints(TargetRefPoints, SourceRefPoints, TargetObj, SourceObj, radius):
    IcpVidDict = {TargetObj: [], SourceObj: []}

    for obj in [TargetObj, SourceObj]:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="DESELECT")
        bpy.ops.object.mode_set(mode="OBJECT")
        if obj == TargetObj:
            for RefTargetP in TargetRefPoints:
                RefCo = RefTargetP.location
                RadiusVertsIds, RadiusVertsCo, RadiusVertsDistance = KdRadiusVerts(
                    TargetObj, RefCo, radius
                )
                IcpVidDict[TargetObj].extend(RadiusVertsIds)
                for idx in RadiusVertsIds:
                    obj.data.vertices[idx].select = True

        if obj == SourceObj:
            for RefSourceP in SourceRefPoints:
                RefCo = RefSourceP.location
                RadiusVertsIds, RadiusVertsCo, RadiusVertsDistance = KdRadiusVerts(
                    SourceObj, RefCo, radius
                )
                IcpVidDict[SourceObj].extend(RadiusVertsIds)
                for idx in RadiusVertsIds:
                    obj.data.vertices[idx].select = True

        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

        ICP_VGroup = obj.vertex_groups.new(name="BDENTAL_ICP_VG")
        obj.vertex_groups.active = ICP_VGroup
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.object.vertex_group_assign()
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")

    for obj in [TargetObj, SourceObj]:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = TargetObj

    return IcpVidDict


def KdIcpPairsToTransformMatrix(
    TargetKdList, SourceKdList
):  # SourceKdList, TargetKdList
    # TransformMatrix = Matrix()  # identity Matrix (4x4)

    # make 2 arrays of coordinates :
    TargetArray = np.array(TargetKdList, dtype=np.float64).T
    SourceArray = np.array(SourceKdList, dtype=np.float64).T

    # Calculate centers of Target and Source RefPoints :
    TargetCenter, SourceCenter = np.mean(TargetArray, axis=1), np.mean(
        SourceArray, axis=1
    )

    # Calculate Translation :
    ###################################

    # TransMatrix_1 : Matrix(4x4) will translate center of SourceRefPoints...
    # to origine (0,0,0) location.
    TransMatrix_1 = Matrix.Translation(Vector(-SourceCenter))

    # TransMatrix_2 : Matrix(4x4) will translate center of SourceRefPoints...
    #  to the center of TargetRefPoints location.
    TransMatrix_2 = Matrix.Translation(Vector(TargetCenter))

    # Calculate Rotation :
    ###################################

    # Home Arrays will get the Centered Target and Source RefPoints around origin (0,0,0).
    HomeTargetArray, HomeSourceArray = (
        TargetArray - TargetCenter.reshape(3, 1),
        SourceArray - SourceCenter.reshape(3, 1),
    )
    # Rigid transformation via SVD of covariance matrix :
    U, S, Vt = np.linalg.svd(np.dot(HomeTargetArray, HomeSourceArray.T))

    # rotation matrix from SVD orthonormal bases :
    R = np.dot(U, Vt)
    if np.linalg.det(R) < 0.0:
        Vt[2, :] *= -1
        R = np.dot(U, Vt)
        print(" Reflection fixed ")

    RotationMatrix = Matrix(R).to_4x4()
    TransformMatrix = TransMatrix_2 @ RotationMatrix @ TransMatrix_1

    return TransformMatrix


# # TODO= fix loop iterations ...!
# def GaussNewtonIcpAlgorythm(
#     SourceKdList,
#     TargetKdList,
#     initial=np.array(
#         [radians(1)],
#         [radians(1)],
#         [radians(1)],
#         [1],
#         [1],
#         [1],
#     ),
#     loop,
# ):

#     RangePoints = min(len(SourceKdList), len(TargetKdList))
#     J, e = [], []

#     for i in range(RangePoints):

#         sx = SourceKdList[i][0]
#         sy = SourceKdList[i][1]
#         sz = SourceKdList[i][2]

#         dx = TargetKdList[i][0]
#         dy = TargetKdList[i][1]
#         dz = TargetKdList[i][2]

#         alpha = initial[0][0]
#         beta = initial[1][0]
#         gamma = initial[2][0]
#         tx = initial[3][0]
#         ty = initial[4][0]
#         tz = initial[5][0]

#         a1 = (
#             (-2 * beta * sx * sy)
#             - (2 * gamma * sx * sz)
#             + (2 * alpha * ((sy * sy) + (sz * sz)))
#             + (2 * ((sz * dy) - (sy * dz)))
#             + 2 * ((sy * tz) - (sz * ty))
#         )
#         a2 = (
#             (-2 * alpha * sx * sy)
#             - (2 * gamma * sy * sz)
#             + (2 * beta * ((sx * sx) + (sz * sz)))
#             + (2 * ((sx * dz) - (sz * dx)))
#             + 2 * ((sz * tx) - (sx * tz))
#         )
#         a3 = (
#             (-2 * alpha * sx * sz)
#             - (2 * beta * sy * sz)
#             + (2 * gamma * ((sx * sx) + (sy * sy)))
#             + (2 * ((sy * dx) - (sx * dy)))
#             + 2 * ((sx * ty) - (sy * tx))
#         )
#         a4 = 2 * (sx - (gamma * sy) + (beta * sz) + tx - dx)
#         a5 = 2 * (sy - (alpha * sz) + (gamma * sx) + ty - dy)
#         a6 = 2 * (sz - (beta * sx) + (alpha * sy) + tz - dz)

#         _residual = (a4 * a4 / 4) + (a5 * a5 / 4) + (a6 * a6 / 4)

#         _J = np.array([a1, a2, a3, a4, a5, a6])
#         _e = np.array([_residual])

#         J.append(_J)
#         e.append(_e)

#     jacobian = np.array(J)
#     residual = np.array(e)

#     update = -np.dot(
#         np.dot(
#             np.linalg.pinv(np.dot(np.transpose(jacobian), jacobian)),
#             np.transpose(jacobian),
#         ),
#         residual,
#     )

#     # print update, initial

#     initial = initial + update

#     print(initial.T)

#     loop = loop + 1

#     if (
#         loop < 20
#     ):  # here lies the control variable, control the number of iteration from here

#         icp_point_to_point_lm(source_points, dest_points, initial, loop)

#     alpha = initial[0][0]
#     beta = initial[1][0]
#     gamma = initial[2][0]
#     tx = initial[3][0]
#     ty = initial[4][0]
#     tz = initial[5][0]

#     EULER3D = Euler((alpha, beta, gamma), "XYZ")
#     RotMat = EULER3D.to_matrix().to_4x4()

#     print(f"Euler : {EULER3D}")
#     print(f"Rotation Matrix: {RotMat}")

#     Trans3D = Vector((tx, ty, tz))
#     TransMat = Matrix.Translation(Trans3D)
#     print(f"Translation Matrix: {TransMat}")

#     TransformMatrix = TransMat @ RotMat
#     print(f"Transformation Matrix: {TransformMatrix}")

#     return TransformMatrix


# def icp_point_to_point_lm(source_points, dest_points,initial,loop):
#     """
#     Point to point matching using Gauss-Newton

#     source_points:  nx3 matrix of n 3D points
#     dest_points: nx3 matrix of n 3D points, which have been obtained by some rigid deformation of 'source_points'
#     initial: 1x6 matrix, denoting alpha, beta, gamma (the Euler angles for rotation and tx, ty, tz (the translation along three axis).
#                 this is the initial estimate of the transformation between 'source_points' and 'dest_points'
#     loop: start with zero, to keep track of the number of times it loops, just a very crude way to control the recursion

#     """

#     J = []
#     e = []

#     for i in range (0,dest_points.shape[0]-1):

#         #print dest_points[i][3],dest_points[i][4],dest_points[i][5]
#         dx = dest_points[i][0]
#         dy = dest_points[i][1]
#         dz = dest_points[i][2]

#         sx = source_points[i][0]
#         sy = source_points[i][1]
#         sz = source_points[i][2]

#         alpha = initial[0][0]
#         beta = initial[1][0]
#         gamma = initial[2][0]
#         tx = initial[3][0]
#         ty = initial[4][0]
#         tz = initial[5][0]
#         #print alpha

#         a1 = (-2*beta*sx*sy) - (2*gamma*sx*sz) + (2*alpha*((sy*sy) + (sz*sz))) + (2*((sz*dy) - (sy*dz))) + 2*((sy*tz) - (sz*ty))
#         a2 = (-2*alpha*sx*sy) - (2*gamma*sy*sz) + (2*beta*((sx*sx) + (sz*sz))) + (2*((sx*dz) - (sz*dx))) + 2*((sz*tx) - (sx*tz))
#         a3 = (-2*alpha*sx*sz) - (2*beta*sy*sz) + (2*gamma*((sx*sx) + (sy*sy))) + (2*((sy*dx) - (sx*dy))) + 2*((sx*ty) - (sy*tx))
#         a4 = 2*(sx - (gamma*sy) + (beta*sz) +tx -dx)
#         a5 = 2*(sy - (alpha*sz) + (gamma*sx) +ty -dy)
#         a6 = 2*(sz - (beta*sx) + (alpha*sy) +tz -dz)

#         _residual = (a4*a4/4)+(a5*a5/4)+(a6*a6/4)

#         _J = np.array([a1, a2, a3, a4, a5, a6])
#         _e = np.array([_residual])

#         J.append(_J)
#         e.append(_e)

#     jacobian = np.array(J)
#     residual = np.array(e)

#     update = -np.dot(np.dot(np.linalg.pinv(np.dot(np.transpose(jacobian),jacobian)),np.transpose(jacobian)),residual)

#     #print update, initial

#     initial = initial + update

#     print np.transpose(initial)

#     loop = loop + 1

#     if(loop < 50):  # here lies the control variable, control the number of iteration from here

#         icp_point_to_point_lm(source_points,dest_points,initial, loop)


# def BvertsToVtkPolyData2(VcoList):
#     VtkArray = vtk.vtkFloatArray()
#     VtkArray.SetNumberOfComponents(3)
#     VtkArray.SetNumberOfTuples(len(VcoList))
#     for i, co in enumerate(VcoList):
#         VtkArray.SetTuple3(i, co[0], co[1], co[2])
#     VtkPoints = vtk.vtkPoints()
#     VtkPoints.SetData(VtkArray)
#     VtkPolyData = vtk.vtkPolyData()
#     VtkPolyData.SetPoints(VtkPoints)
#     return VtkPolyData


# VcoList = [(1, 1, 1), (2, 2, 2), (0, 1, -2)]
# start = Tcounter()

# VtkPolyData1 = BvertsToVtkPolyData1(VcoList)
# print(VtkPolyData1)
# T1 = Tcounter()
# print(f"PolyData1 finished in {T1-start} secondes")
