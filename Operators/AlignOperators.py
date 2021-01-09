import time, os, sys, shutil, math, threading, platform, subprocess, string
from math import degrees, radians, pi, ceil, floor
import numpy as np
from time import sleep, perf_counter as Tcounter
from queue import Queue

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


from .BDENTAL_Utils import *
from .BDENTAL_ALIGN_Utils import *


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
        matName = "BaseRefMat"
    if name.startswith("M"):
        matName = "AlignRefMat"

    mat = bpy.data.materials.get(matName) or bpy.data.materials.new(matName)
    mat.diffuse_color = color
    mat.use_nodes = True
    RefP.active_material = mat
    RefP.show_name = True
    return RefP


def RefPointsToTransformMatrix(BaseRefPoints, AlignRefPoints):
    # TransformMatrix = Matrix()  # identity Matrix (4x4)

    # make 2 arrays of coordinates :
    BaseArray = np.array([obj.location for obj in BaseRefPoints], dtype=np.float64).T
    AlignArray = np.array([obj.location for obj in AlignRefPoints], dtype=np.float64).T

    # Calculate centers of Base and Align RefPoints :
    BaseCenter, AlignCenter = np.mean(BaseArray, axis=1), np.mean(AlignArray, axis=1)

    # Calculate Translation :
    ###################################

    # TransMatrix_1 : Matrix(4x4) will translate center of AlignRefPoints...
    # to origine (0,0,0) location.
    TransMatrix_1 = Matrix.Translation(Vector(-AlignCenter))

    # TransMatrix_2 : Matrix(4x4) will translate center of AlignRefPoints...
    #  to the center of BaseRefPoints location.
    TransMatrix_2 = Matrix.Translation(Vector(BaseCenter))

    # Calculate Rotation :
    ###################################

    # Home Arrays will get the Centered Base and Align RefPoints around origin (0,0,0).
    HomeBaseArray, HomeAlignArray = (
        BaseArray - BaseCenter.reshape(3, 1),
        AlignArray - AlignCenter.reshape(3, 1),
    )
    # Rigid transformation via SVD of covariance matrix :
    U, S, Vt = np.linalg.svd(np.dot(HomeBaseArray, HomeAlignArray.T))

    # rotation matrix from SVD orthonormal bases :
    R = np.dot(U, Vt)
    if np.linalg.det(R) < 0.0:
        Vt[2, :] *= -1
        R = np.dot(U, Vt)
        print(" Reflection fixed ")

    RotationMatrix = Matrix(R).to_4x4()
    TransformMatrix = TransMatrix_2 @ RotationMatrix @ TransMatrix_1

    return TransformMatrix


############################################################################
class BDENTAL_OT_AlignPoints(bpy.types.Operator):
    """ Add Align Refference points """

    bl_idname = "bdental.alignpoints"
    bl_label = "ALIGN POINTS"
    bl_options = {"REGISTER", "UNDO"}

    BaseColor = (1, 0, 0, 1)  # red
    AlignColor = (0, 0, 1, 1)  # blue
    CollName = "ALIGN POINTS"
    BaseChar = "B"
    AlignChar = "A"

    def modal(self, context, event):

        ############################################
        if not event.type in {
            self.BaseChar,
            self.AlignChar,
            "DEL",
            "RET",
            "ESC",
        }:
            # allow navigation

            return {"PASS_THROUGH"}
        #########################################
        if event.type == self.BaseChar:
            # Add Base Refference point :
            if event.value == ("PRESS"):
                color = self.BaseColor
                CollName = self.CollName
                self.BaseCounter += 1
                name = f"B{self.BaseCounter}"
                RefP = AddRefPoint(name, color, CollName)
                self.BaseRefPoints.append(RefP)
                self.TotalRefPoints.append(RefP)
                bpy.ops.object.select_all(action="DESELECT")

        #########################################
        if event.type == self.AlignChar:
            # Add Base Refference point :
            if event.value == ("PRESS"):
                color = self.AlignColor
                CollName = self.CollName
                self.AlignCounter += 1
                name = f"M{self.AlignCounter}"
                RefP = AddRefPoint(name, color, CollName)
                self.AlignRefPoints.append(RefP)
                self.TotalRefPoints.append(RefP)
                bpy.ops.object.select_all(action="DESELECT")

        ###########################################
        elif event.type == ("DEL"):
            if event.value == ("PRESS"):
                if self.TotalRefPoints:
                    obj = self.TotalRefPoints.pop()
                    name = obj.name
                    if name.startswith("B"):
                        self.BaseCounter -= 1
                        self.BaseRefPoints.pop()
                    if name.startswith("M"):
                        self.AlignCounter -= 1
                        self.AlignRefPoints.pop()
                    bpy.data.objects.remove(obj)
                    bpy.ops.object.select_all(action="DESELECT")

        ###########################################
        elif event.type == "RET":

            if event.value == ("PRESS"):

                #############################################
                condition = (
                    len(self.BaseRefPoints) == len(self.AlignRefPoints)
                    and len(self.BaseRefPoints) >= 3
                )
                if not condition:
                    message = [
                        "          Please check the following :",
                        "   - The number of Base Refference points and,",
                        "       Align Refference points should match!",
                        "   - The number of Base Refference points ,",
                        "         and Align Refference points,",
                        "       should be superior or equal to 3",
                        "        <<Please check and retry !>>",
                    ]
                    ShowMessageBox(message=message, icon="COLORSET_02_VEC")

                else:
                    TransformMatrix = RefPointsToTransformMatrix(
                        self.BaseRefPoints, self.AlignRefPoints
                    )

                    self.AlignObject.matrix_world = (
                        TransformMatrix @ self.AlignObject.matrix_world
                    )
                    for obj in self.TotalRefPoints:
                        bpy.data.objects.remove(obj)

                    ##########################################################
                    bpy.context.space_data.overlay.show_outline_selected = True
                    bpy.context.space_data.overlay.show_object_origins = True
                    bpy.context.space_data.overlay.show_annotation = True
                    bpy.context.space_data.overlay.show_text = True
                    bpy.context.space_data.overlay.show_extras = True
                    bpy.context.space_data.overlay.show_floor = True
                    bpy.context.space_data.overlay.show_axis_x = True
                    bpy.context.space_data.overlay.show_axis_y = True
                    ###########################################################

                    bpy.ops.object.hide_view_clear()
                    bpy.ops.object.select_all(action="DESELECT")
                    for obj in self.visibleObjects:
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = obj
                    bpy.ops.object.hide_view_set(unselected=True)
                    bpy.ops.object.select_all(action="DESELECT")
                    bpy.ops.wm.tool_set_by_id(name="builtin.select")
                    bpy.context.scene.tool_settings.use_snap = False
                    bpy.context.space_data.shading.background_color = (
                        self.background_color
                    )
                    bpy.context.space_data.shading.background_type = (
                        self.background_type
                    )
                    print(self.background_type, self.background_color)
                    BDENTAL_Props = context.scene.BDENTAL_Props
                    BDENTAL_Props.AlignModalState = False
                    bpy.context.scene.cursor.location = (0, 0, 0)
                    return {"FINISHED"}

        ###########################################
        elif event.type == ("ESC"):

            if event.value == ("PRESS"):

                for RefP in self.TotalRefPoints:
                    bpy.data.objects.remove(RefP)

                ##########################################################
                bpy.context.space_data.overlay.show_outline_selected = True
                bpy.context.space_data.overlay.show_object_origins = True
                bpy.context.space_data.overlay.show_annotation = True
                bpy.context.space_data.overlay.show_text = True
                bpy.context.space_data.overlay.show_extras = True
                bpy.context.space_data.overlay.show_floor = True
                bpy.context.space_data.overlay.show_axis_x = True
                bpy.context.space_data.overlay.show_axis_y = True
                ###########################################################

                bpy.ops.object.hide_view_clear()
                bpy.ops.object.select_all(action="DESELECT")
                for obj in self.visibleObjects:
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj
                bpy.ops.object.hide_view_set(unselected=True)
                bpy.ops.object.select_all(action="DESELECT")
                bpy.ops.wm.tool_set_by_id(name="builtin.select")
                bpy.context.scene.tool_settings.use_snap = False
                bpy.context.space_data.shading.background_color = self.background_color
                bpy.context.space_data.shading.background_type = self.background_type
                BDENTAL_Props = context.scene.BDENTAL_Props
                BDENTAL_Props.AlignModalState = False
                bpy.context.scene.cursor.location = (0, 0, 0)
                message = [
                    " The Align Operation was Cancelled!",
                ]

                ShowMessageBox(message=message, icon="COLORSET_03_VEC")
                return {"CANCELLED"}

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        Condition_1 = len(bpy.context.selected_objects) != 2
        Condition_2 = bpy.context.selected_objects and not bpy.context.active_object
        Condition_3 = bpy.context.selected_objects and not (
            bpy.context.active_object in bpy.context.selected_objects
        )

        if Condition_1 or Condition_2 or Condition_3:

            message = [
                "Selection is invalid !",
                "Please Deselect all objects,",
                "Select the Object to Align and ,",
                "<SHIFT + Select> the Base Object.",
                "Click info button for more info.",
            ]
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")

            return {"CANCELLED"}

        else:

            if context.space_data.type == "VIEW_3D":
                BDENTAL_Props = context.scene.BDENTAL_Props
                BDENTAL_Props.AlignModalState = True

                # Prepare scene  :

                self.BaseObject = bpy.context.active_object
                self.AlignObject = [
                    obj
                    for obj in bpy.context.selected_objects
                    if not obj is self.BaseObject
                ][0]

                self.BaseRefPoints = []
                self.AlignRefPoints = []
                self.TotalRefPoints = []

                self.BaseCounter = 0
                self.AlignCounter = 0
                self.visibleObjects = bpy.context.visible_objects.copy()
                self.background_type = bpy.context.space_data.shading.background_type
                bpy.context.space_data.shading.background_type = "VIEWPORT"
                self.background_color = tuple(
                    bpy.context.space_data.shading.background_color
                )
                bpy.context.space_data.shading.background_color = (0.0, 0.0, 0.0)

                ##########################################################
                bpy.context.space_data.overlay.show_outline_selected = False
                bpy.context.space_data.overlay.show_object_origins = False
                bpy.context.space_data.overlay.show_annotation = False
                bpy.context.space_data.overlay.show_text = False
                bpy.context.space_data.overlay.show_extras = False
                bpy.context.space_data.overlay.show_floor = False
                bpy.context.space_data.overlay.show_axis_x = False
                bpy.context.space_data.overlay.show_axis_y = False
                ###########################################################
                bpy.context.scene.tool_settings.use_snap = True
                bpy.context.scene.tool_settings.snap_elements = {"FACE"}
                bpy.context.scene.tool_settings.transform_pivot_point = (
                    "INDIVIDUAL_ORIGINS"
                )
                bpy.ops.wm.tool_set_by_id(name="builtin.cursor")
                bpy.ops.object.hide_view_set(unselected=True)

                # bpy.ops.object.select_all(action="DESELECT")
                context.window_manager.modal_handler_add(self)

                return {"RUNNING_MODAL"}

            else:

                self.report({"WARNING"}, "Active space must be a View3d")

                return {"CANCELLED"}


class BDENTAL_OT_AlignPointsInfo(bpy.types.Operator):
    """ Add Align Refference points """

    bl_idname = "bdental.alignpointsinfo"
    bl_label = "INFO"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        message = [
            "\u2588 Deselect all objects,",
            "\u2588 Select the Object to Align,",
            "\u2588 Press <SHIFT + Click> to select the Base Object,",
            "\u2588 Click <ALIGN POINTS> button,",
            f"      Press <Left Click> to Place Cursor,",
            f"      Press <'B'> to Add red Point (Base),",
            f"      Press <'A'> to Add blue Point (Align),",
            f"      Press <'DEL'> to delete Point,",
            f"      Press <'ESC'> to Cancel Operation,",
            f"      Press <'ENTER'> to execute Alignement.",
            "\u2588 NOTE :",
            "3 Red Points and 3 Blue Points,",
            "are the minimum required for Points Alignement!",
        ]
        ShowMessageBox(message=message, title="INFO", icon="INFO")

        return {"FINISHED"}


class BDENTAL_OT_AlignICP(bpy.types.Operator):
    """ Iterative closest point Alignement """

    bl_idname = "bdental.alignicp"
    bl_label = "ICP ALIGN"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):

        Condition_1 = len(bpy.context.selected_objects) != 2
        Condition_2 = bpy.context.selected_objects and not bpy.context.active_object
        Condition_3 = bpy.context.selected_objects and not (
            bpy.context.active_object in bpy.context.selected_objects
        )

        if Condition_1 or Condition_2 or Condition_3:

            message = [
                "Selection is invalid !",
                "Please Deselect all objects,",
                "Select the Object to Align and ,",
                "<SHIFT + Select> the Base Object.",
                "Click info button for more info.",
            ]
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")

            return {"CANCELLED"}

        else:

            BDENTAL_Props = context.scene.BDENTAL_Props
            AlignModalState = BDENTAL_Props.AlignModalState

            start = Tcounter()

            BaseObject = context.object
            AlignObject = [
                obj for obj in bpy.context.selected_objects if not obj is BaseObject
            ][0]

            def IcpPipline():
                SourceVcoList = ObjectToIcpVcoList(obj=AlignObject, VG=False)
                TargetVcoList = ObjectToIcpVcoList(obj=BaseObject, VG=False)

                SourceVcoList, TargetVcoList = KdIcpPairs(
                    SourceVcoList, TargetVcoList, VertsLimite=10000
                )

                TransformMatrix = VtkICPTransform(
                    SourceVcoList=SourceVcoList,
                    TargetVcoList=TargetVcoList,
                    iterations=30,
                    Precision=0.0000001,
                )

                AlignObject.matrix_world = TransformMatrix @ AlignObject.matrix_world
                context.view_layer.update()
                for obj in [AlignObject, BaseObject]:
                    obj.update_tag()
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = BaseObject

            for _ in range(2):
                IcpPipline()

            # bpy.ops.object.select_all(action="DESELECT")
            # print(f"TransformMatrix : {TransformMatrix}")
            finish = Tcounter()

            print(f"total time : {finish-start} seconds")

            return {"FINISHED"}


#############################################################################
classes = [BDENTAL_OT_AlignPoints, BDENTAL_OT_AlignPointsInfo, BDENTAL_OT_AlignICP]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
