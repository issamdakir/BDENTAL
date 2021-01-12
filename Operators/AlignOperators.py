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


############################################################################
class BDENTAL_OT_AlignPoints(bpy.types.Operator):
    """ Add Align Refference points """

    bl_idname = "bdental.alignpoints"
    bl_label = "ALIGN POINTS"
    bl_options = {"REGISTER", "UNDO"}

    TargetColor = (1, 0, 0, 1)  # red
    SourceColor = (0, 0, 1, 1)  # blue
    CollName = "ALIGN POINTS"
    TargetChar = "B"
    SourceChar = "A"

    def modal(self, context, event):

        ############################################
        if not event.type in {
            self.TargetChar,
            self.SourceChar,
            "DEL",
            "RET",
            "ESC",
        }:
            # allow navigation

            return {"PASS_THROUGH"}
        #########################################
        if event.type == self.TargetChar:
            # Add Target Refference point :
            if event.value == ("PRESS"):
                color = self.TargetColor
                CollName = self.CollName
                self.TargetCounter += 1
                name = f"B{self.TargetCounter}"
                RefP = AddRefPoint(name, color, CollName)
                self.TargetRefPoints.append(RefP)
                self.TotalRefPoints.append(RefP)
                bpy.ops.object.select_all(action="DESELECT")

        #########################################
        if event.type == self.SourceChar:
            # Add Source Refference point :
            if event.value == ("PRESS"):
                color = self.SourceColor
                CollName = self.CollName
                self.SourceCounter += 1
                name = f"M{self.SourceCounter}"
                RefP = AddRefPoint(name, color, CollName)
                self.SourceRefPoints.append(RefP)
                self.TotalRefPoints.append(RefP)
                bpy.ops.object.select_all(action="DESELECT")

        ###########################################
        elif event.type == ("DEL"):
            if event.value == ("PRESS"):
                if self.TotalRefPoints:
                    obj = self.TotalRefPoints.pop()
                    name = obj.name
                    if name.startswith("B"):
                        self.TargetCounter -= 1
                        self.TargetRefPoints.pop()
                    if name.startswith("M"):
                        self.SourceCounter -= 1
                        self.SourceRefPoints.pop()
                    bpy.data.objects.remove(obj)
                    bpy.ops.object.select_all(action="DESELECT")

        ###########################################
        elif event.type == "RET":

            if event.value == ("PRESS"):

                start = Tcounter()

                TargetObj = self.TargetObject
                SourceObj = self.SourceObject

                #############################################
                condition = (
                    len(self.TargetRefPoints) == len(self.SourceRefPoints)
                    and len(self.TargetRefPoints) >= 3
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
                        self.TargetRefPoints, self.SourceRefPoints
                    )

                    SourceObj.matrix_world = TransformMatrix @ SourceObj.matrix_world
                    for SourceRefP in self.SourceRefPoints:
                        SourceRefP.matrix_world = (
                            TransformMatrix @ SourceRefP.matrix_world
                        )

                    # Update scene :
                    context.view_layer.update()
                    for obj in [TargetObj, SourceObj]:
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = TargetObj
                        obj.update_tag()

                    # ICP alignement :
                    print("ICP Align processing...")
                    IcpVidDict = VidDictFromPoints(
                        TargetRefPoints=self.TargetRefPoints,
                        SourceRefPoints=self.SourceRefPoints,
                        TargetObj=TargetObj,
                        SourceObj=SourceObj,
                        radius=3,
                    )
                    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
                    BDENTAL_Props.IcpVidDict = str(IcpVidDict)

                    SourceVidList, TargetVidList = (
                        IcpVidDict[SourceObj],
                        IcpVidDict[TargetObj],
                    )

                    for _ in range(30):
                        SourceVcoList = [
                            SourceObj.matrix_world @ SourceObj.data.vertices[idx].co
                            for idx in SourceVidList
                        ]
                        TargetVcoList = [
                            TargetObj.matrix_world @ TargetObj.data.vertices[idx].co
                            for idx in TargetVidList
                        ]
                        SourceKdList, TargetKdList, DistList = KdIcpPairs(
                            SourceVcoList, TargetVcoList, VertsLimite=10000
                        )
                        TransformMatrix = KdIcpPairsToTransformMatrix(
                            TargetKdList=TargetKdList, SourceKdList=SourceKdList
                        )
                        SourceObj.matrix_world = (
                            TransformMatrix @ SourceObj.matrix_world
                        )
                        # Update scene :
                        SourceObj.update_tag()
                        context.view_layer.update()

                        SourceObj = self.SourceObject
                        SourceVcoList = [
                            SourceObj.matrix_world @ SourceObj.data.vertices[idx].co
                            for idx in SourceVidList
                        ]
                        SourceKdList, TargetKdList, DistList = KdIcpPairs(
                            SourceVcoList, TargetVcoList, VertsLimite=10000
                        )
                        MaxDist = max(DistList)
                        print("Max distance = ", MaxDist)
                        if MaxDist < 0.0001:
                            break

                    # TransformMatrix = VtkICPTransform(
                    #     SourceVcoList=SourceVcoList,
                    #     TargetVcoList=TargetVcoList,
                    #     iterations=30,
                    #     Precision=0.0000001,
                    # )

                    # SourceObj.matrix_world = TransformMatrix @ SourceObj.matrix_world
                    # Update scene :
                    # context.view_layer.update()
                    # for obj in [TargetObj, SourceObj]:
                    #     obj.select_set(True)
                    #     bpy.context.view_layer.objects.active = TargetObj
                    #     obj.update_tag()

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

                    BDENTAL_Props = context.scene.BDENTAL_Props
                    BDENTAL_Props.AlignModalState = False
                    bpy.context.scene.cursor.location = (0, 0, 0)

                    for obj in [TargetObj, SourceObj]:
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = TargetObj

                    finish = Tcounter()
                    print(f"Alignement finshed in {finish-start} secondes")

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

                self.TargetObject = bpy.context.active_object
                self.SourceObject = [
                    obj
                    for obj in bpy.context.selected_objects
                    if not obj is self.TargetObject
                ][0]

                self.TargetRefPoints = []
                self.SourceRefPoints = []
                self.TotalRefPoints = []

                self.TargetCounter = 0
                self.SourceCounter = 0
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
            IcpVidDict = eval(BDENTAL_Props.IcpVidDict)

            start = Tcounter()

            TargetObj = context.object
            SourceObj = [
                obj for obj in bpy.context.selected_objects if not obj is TargetObj
            ][0]

            if IcpVidDict:
                if [key for key in IcpVidDict.keys()] == [TargetObj, SourceObj]:

                    SourceVidList, TargetVidList = (
                        IcpVidDict[SourceObj],
                        IcpVidDict[TargetObj],
                    )
            else:
                SourceVidList = [v.index for v in SourceObj.data.vertices]
                TargetVidList = [v.index for v in TargetObj.data.vertices]

            self.IcpPipline(
                context,
                SourceObj,
                TargetObj,
                SourceVidList,
                TargetVidList,
                VertsLimite=10000,
                Iterations=30,
            )

            finish = Tcounter()

            print(f"ICP total time : {finish-start} seconds")

            return {"FINISHED"}

    def IcpPipline(
        self,
        context,
        SourceObj,
        TargetObj,
        SourceVidList,
        TargetVidList,
        VertsLimite,
        Iterations,
    ):

        for _ in range(Iterations):

            SourceVcoList = [
                SourceObj.matrix_world @ SourceObj.data.vertices[idx].co
                for idx in SourceVidList
            ]
            TargetVcoList = [
                TargetObj.matrix_world @ TargetObj.data.vertices[idx].co
                for idx in TargetVidList
            ]
            SourceKdList, TargetKdList, DistList = KdIcpPairs(
                SourceVcoList, TargetVcoList, VertsLimite=10000
            )
            TransformMatrix = KdIcpPairsToTransformMatrix(
                TargetKdList=TargetKdList, SourceKdList=SourceKdList
            )
            SourceObj.matrix_world = TransformMatrix @ SourceObj.matrix_world
            # Update scene :
            SourceObj.update_tag()
            context.view_layer.update()

            SourceVcoList = [
                SourceObj.matrix_world @ SourceObj.data.vertices[idx].co
                for idx in SourceVidList
            ]
            SourceKdList, TargetKdList, DistList = KdIcpPairs(
                SourceVcoList, TargetVcoList, VertsLimite=10000
            )
            MaxDist = max(DistList)
            print("Max distance = ", MaxDist)


#############################################################################
classes = [BDENTAL_OT_AlignPoints, BDENTAL_OT_AlignPointsInfo, BDENTAL_OT_AlignICP]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
