# Python imports :
import time, os, sys, shutil, math, threading, platform, subprocess
from math import degrees, radians, pi
import numpy as np
from time import sleep, perf_counter as counter
from queue import Queue

# Blender Imports :
import bpy
import bmesh
from mathutils import Matrix, Vector, Euler, kdtree
from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    FloatVectorProperty,
    BoolProperty,
)

import SimpleITK as sitk
import cv2
import vtk
from vtk.util import numpy_support
from vtk import vtkCommand


# import BDENTAL_Utils Functions :
from . import BDENTAL_Utils
from .BDENTAL_Utils import *

# Global variables :
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ShadersBlendFile = os.path.join(
    addon_dir, "Resources\BlendData\BDENTAL_BlendData.blend"
)
GpShader = "VGS_Marcos_modified"  # "VGS_Marcos_01" "VGS_Dakir_01"
Wmin = -400
Wmax = 3000
ProgEvent = vtkCommand.ProgressEvent
#######################################################################################
########################### CT Scan Load : Operators ##############################
#######################################################################################
def GetMaxSerie(UserDcmDir):

    SeriesDict = {}
    Series_reader = sitk.ImageSeriesReader()
    series_IDs = Series_reader.GetGDCMSeriesIDs(UserDcmDir)

    if not series_IDs:
        print("No valid DICOM Serie found in DICOM Folder ! ")
        message = "No valid DICOM Serie found in DICOM Folder ! "
        ShowMessageBox(message=message, icon="COLORSET_01_VEC")
        return {"CANCELLED"}

    def GetSerieCount(sID):
        count = len(Series_reader.GetGDCMSeriesFileNames(UserDcmDir, sID))
        SeriesDict[count] = sID

    threads = [
        threading.Thread(
            target=GetSerieCount,
            args=[sID],
            daemon=True,
        )
        for sID in series_IDs
    ]

    for t in threads:
        t.start()

    for t in threads:
        t.join()
    MaxCount = sorted(SeriesDict, reverse=True)[0]
    MaxSerie = SeriesDict[MaxCount]
    return MaxSerie, MaxCount


def Load_Dicom_funtion(context, q):

    ################################################################################################
    start = time.perf_counter()
    print("processing START...")

    ################################################################################################

    BDENTAL_Props = context.scene.BDENTAL_Props
    UserDcmDir = BDENTAL_Props.UserDcmDir
    UserProjectDir = BDENTAL_Props.UserProjectDir

    ################################################################################################

    if not os.path.exists(UserProjectDir):

        message = "The Selected Project Directory Path is not valid ! "
        ShowMessageBox(message=message, icon="COLORSET_02_VEC")
        return {"CANCELLED"}

    elif os.listdir(UserProjectDir):

        message = " Project Folder Should be Empty ! "
        ShowMessageBox(message=message, icon="COLORSET_02_VEC")
        return {"CANCELLED"}

    elif not os.path.exists(UserDcmDir):

        message = " Please use the Folder icon to Select a valid Dicom Directory ! "
        ShowMessageBox(message=message, icon="COLORSET_02_VEC")
        return {"CANCELLED"}

    elif not os.listdir(UserDcmDir):
        message = "No valid DICOM Serie found in DICOM Folder ! "
        ShowMessageBox(message=message, icon="COLORSET_02_VEC")
        return {"CANCELLED"}

    else:
        Series_reader = sitk.ImageSeriesReader()
        MaxSerie, MaxCount = GetMaxSerie(UserDcmDir)
        DcmSerie = Series_reader.GetGDCMSeriesFileNames(UserDcmDir, MaxSerie)

        ##################################### debug_02 ###################################
        debug_01 = time.perf_counter()
        message = f" MaxSerie ID : {MaxSerie}, MaxSerie Count : {MaxCount} ({round(debug_01-start,2)})"
        print(message)
        # q.put("Max DcmSerie extracted...")
        ####################################################################################

        # Get StudyInfo :
        reader = sitk.ImageFileReader()
        reader.SetFileName(DcmSerie[0])
        reader.LoadPrivateTagsOn()
        reader.ReadImageInformation()

        Image3D = sitk.ReadImage(DcmSerie)

        # Get Dicom Info :
        Sp = Spacing = Image3D.GetSpacing()
        Sz = Size = Image3D.GetSize()
        Dims = Dimensions = Image3D.GetDimension()
        Origin = Image3D.GetOrigin()
        Direction = Image3D.GetDirection()

        # calculate Informations :
        D = Direction
        O = Origin
        DirectionMatrix_4x4 = Matrix(
            (
                (D[0], D[1], D[2], 0.0),
                (D[3], D[4], D[5], 0.0),
                (D[6], D[7], D[8], 0.0),
                (0.0, 0.0, 0.0, 1.0),
            )
        )

        TransMatrix_4x4 = Matrix(
            (
                (1.0, 0.0, 0.0, O[0]),
                (0.0, 1.0, 0.0, O[1]),
                (0.0, 0.0, 1.0, O[2]),
                (0.0, 0.0, 0.0, 1.0),
            )
        )

        VtkTransform_4x4 = TransMatrix_4x4 @ DirectionMatrix_4x4
        P0 = Image3D.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
        P_diagonal = Image3D.TransformContinuousIndexToPhysicalPoint(
            (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
        )
        VCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5

        C = VCenter

        TransformMatrix = Matrix(
            (
                (D[0], D[1], D[2], C[0]),
                (D[3], D[4], D[5], C[1]),
                (D[6], D[7], D[8], C[2]),
                (0.0, 0.0, 0.0, 1.0),
            )
        )

        # Set DcmInfo :

        BDENTAL_Props.Wmin = Wmin
        BDENTAL_Props.Wmax = Wmax

        DcmInfo = {
            "PixelType": Image3D.GetPixelIDTypeAsString(),
            "Wmin": Wmin,
            "Wmax": Wmax,
            "Size": Sz,
            "Dims": Dims,
            "Spacing": Sp,
            "Origin": Origin,
            "Direction": Direction,
            "TransformMatrix": TransformMatrix,
            "DirectionMatrix_4x4": DirectionMatrix_4x4,
            "TransMatrix_4x4": TransMatrix_4x4,
            "VtkTransform_4x4": VtkTransform_4x4,
            "VolumeCenter": VCenter,
        }

        tags = {
            "StudyDate": "0008|0020",
            "PatientName": "0010|0010",
            "PatientID": "0010|0020",
            "BirthDate": "0010|0030",
            "WinCenter": "0028|1050",
            "WinWidth": "0028|1051",
        }
        for k, tag in tags.items():
            if tag in reader.GetMetaDataKeys():
                v = reader.GetMetaData(tag)
                DcmInfo[k] = v

            else:
                v = ""

            DcmInfo[k] = v
            Image3D.SetMetaData(tag, v)

        # Set DcmInfo property :
        BDENTAL_Props.DcmInfo = str(DcmInfo)

        ###################################### debug_02 ##################################
        debug_02 = time.perf_counter()
        message = f"DcmInfo set done in {debug_02-debug_01}"
        print(message)
        # q.put("Dicom Info extracted...")
        ##################################################################################

        #######################################################################################
        # Add directories :
        SlicesDir = os.path.join(UserProjectDir, "Slices")
        if not os.path.exists(SlicesDir):
            os.makedirs(SlicesDir)
        BDENTAL_Props.SlicesDir = SlicesDir

        PngDir = os.path.join(UserProjectDir, "PNG")
        if not os.path.exists(PngDir):
            os.makedirs(PngDir)
        BDENTAL_Props.PngDir = PngDir

        PatientName = DcmInfo["PatientName"]
        PatientID = DcmInfo["PatientID"]
        Preffix = PatientName or PatientID
        if Preffix:
            # NrrdHuPath = os.path.join(UserProjectDir, f"{Preffix}_Image3DHu.nrrd")
            Nrrd255Path = os.path.join(UserProjectDir, f"{Preffix}_Image3D255.nrrd")
        else:
            # NrrdHuPath = os.path.join(UserProjectDir, "Image3DHu.nrrd")
            Nrrd255Path = os.path.join(UserProjectDir, "Image3D255.nrrd")
        # BDENTAL_Props.NrrdHuPath = NrrdHuPath
        BDENTAL_Props.Nrrd255Path = Nrrd255Path

        #######################################################################################
        # set IntensityWindowing  :
        Image3D_255 = sitk.Cast(
            sitk.IntensityWindowing(
                Image3D,
                windowMinimum=Wmin,
                windowMaximum=Wmax,
                outputMinimum=0.0,
                outputMaximum=255.0,
            ),
            sitk.sitkUInt8,
        )

        # Convert Dicom to nrrd file :
        # sitk.WriteImage(Image3D, NrrdHuPath)
        sitk.WriteImage(Image3D_255, Nrrd255Path)

        ################################## debug_03 ######################################
        debug_03 = time.perf_counter()
        message = f"Nrrd255 written to Project directory, done in {debug_03-debug_02}"
        print(message)
        # q.put("nrrd 3D image file saved...")
        ##################################################################################

        #############################################################################################
        # MultiThreading PNG Writer:
        #########################################################################################
        def Image3DToPNG(i, slices, PngDir):
            img_Slice = slices[i]
            img_Name = "img_{0:04d}.png".format(i)
            img_Out = os.path.join(PngDir, img_Name)
            cv2.imwrite(img_Out, img_Slice)
            # sitk.WriteImage(img_Slice, img_Out)
            # print(f"{img_Name} was processed...")

        #########################################################################################
        # Get slices list :
        Array = sitk.GetArrayFromImage(Image3D_255)
        slices = [np.flipud(Array[i, :, :]) for i in range(Array.shape[0])]
        # slices = [Image3D_255[:, :, i] for i in range(Image3D_255.GetDepth())]
        threads = [
            threading.Thread(
                target=Image3DToPNG,
                args=[i, slices, PngDir],
                daemon=True,
            )
            for i in range(len(slices))
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        #################################### debug_04 ####################################
        debug_04 = time.perf_counter()
        message = f"PNG images written to PNG directory, done in {debug_04-debug_03}"
        print(message)
        # q.put("PNG images saved...")
        ##################################################################################

        if Preffix:
            BlendFile = f"{Preffix}SCAN.blend"
        else:
            BlendFile = "SCAN.blend"
        Blendpath = os.path.join(BDENTAL_Props.UserProjectDir, BlendFile)
        bpy.ops.wm.save_as_mainfile(filepath=Blendpath)

        #################################### debug_05 ####################################
        debug_05 = time.perf_counter()
        message = (
            f"Blender project saved to Project directory, done in {debug_05-debug_04}"
        )
        print(message)
        # q.put("Blender project saved...")
        ##################################################################################

        #############################################################################################
        finish = time.perf_counter()
        message = f"FINISHED in {finish-start} secondes"
        print(message)
        # q.put(message)
        #############################################################################################

    ####### End Load_Dicom_fuction ##############


# BDENTAL CT Scan Series Load :
class BDENTAL_OT_Load_DICOM_Series(bpy.types.Operator):
    """ Load scan infos """

    bl_idname = "bdental.load_dicom_series"
    bl_label = "OPEN SCAN"

    q = Queue()

    def execute(self, context):

        Load_Dicom_funtion(context, self.q)

        message = "DICOM loaded successfully. "
        ShowMessageBox(message=message, icon="COLORSET_03_VEC")

        return {"FINISHED"}


#######################################################################################
# BDENTAL CT Scan 3DImage File Load :
class BDENTAL_OT_Load_3DImage_File(bpy.types.Operator):
    """ Load scan infos """

    bl_idname = "bdental.load_3dimage_file"
    bl_label = "OPEN SCAN"

    def execute(self, context):

        BDENTAL_Props = context.scene.BDENTAL_Props
        UserImageFile = BDENTAL_Props.UserImageFile
        UserProjectDir = BDENTAL_Props.UserProjectDir

        #######################################################################################
        # 1rst check if paths are valid and supported :

        if not os.path.exists(UserProjectDir):

            message = "The Selected Project Directory Path is not valid ! "
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")
            return {"CANCELLED"}

        if os.listdir(UserProjectDir):

            message = " Project Folder Should be Empty ! "
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")
            return {"CANCELLED"}

        if not os.path.exists(UserImageFile):
            message = " Please use the Image File icon to Select a valid Image File ! "
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")
            return {"CANCELLED"}

        reader = sitk.ImageFileReader()
        IO = reader.GetImageIOFromFileName(UserImageFile)
        FileExt = os.path.splitext(UserImageFile)[1]

        if not IO:
            message = f"{FileExt} files are not Supported! for more info about supported files please refer to Addon wiki "
            ShowMessageBox(message=message, icon="COLORSET_01_VEC")
            return {"CANCELLED"}

        Image3D = sitk.ReadImage(UserImageFile)
        Depth = Image3D.GetDepth()

        if Depth == 0:
            message = "Can't Build 3D Volume from 2D Image ! for more info about supported files please refer to Addon wiki"
            ShowMessageBox(message=message, icon="COLORSET_01_VEC")
            return {"CANCELLED"}
        if not Image3D.GetPixelIDTypeAsString() in [
            "32-bit signed integer",
            "16-bit signed integer",
        ]:
            message = "Only Images with Hunsfield data are supported !"
            ShowMessageBox(message=message, icon="COLORSET_01_VEC")
            return {"CANCELLED"}
        ###########################################################################################################

        else:

            print("processing START...")
            start = time.perf_counter()
            ####################################
            Image3D = sitk.ReadImage(UserImageFile)
            # Get Dicom Info :
            Sp = Spacing = Image3D.GetSpacing()
            Sz = Size = Image3D.GetSize()
            Dims = Dimensions = Image3D.GetDimension()
            Origin = Image3D.GetOrigin()
            Direction = Image3D.GetDirection()

            # calculate Informations :
            D = Direction
            O = Origin
            DirectionMatrix_4x4 = Matrix(
                (
                    (D[0], D[1], D[2], 0.0),
                    (D[3], D[4], D[5], 0.0),
                    (D[6], D[7], D[8], 0.0),
                    (0.0, 0.0, 0.0, 1.0),
                )
            )

            TransMatrix_4x4 = Matrix(
                (
                    (1.0, 0.0, 0.0, O[0]),
                    (0.0, 1.0, 0.0, O[1]),
                    (0.0, 0.0, 1.0, O[2]),
                    (0.0, 0.0, 0.0, 1.0),
                )
            )

            VtkTransform_4x4 = TransMatrix_4x4 @ DirectionMatrix_4x4
            P0 = Image3D.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
            P_diagonal = Image3D.TransformContinuousIndexToPhysicalPoint(
                (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
            )
            VCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5

            C = VCenter

            TransformMatrix = Matrix(
                (
                    (D[0], D[1], D[2], C[0]),
                    (D[3], D[4], D[5], C[1]),
                    (D[6], D[7], D[8], C[2]),
                    (0.0, 0.0, 0.0, 1.0),
                )
            )

            # Set DcmInfo :

            BDENTAL_Props.Wmin = Wmin
            BDENTAL_Props.Wmax = Wmax

            DcmInfo = {
                "PixelType": Image3D.GetPixelIDTypeAsString(),
                "Wmin": Wmin,
                "Wmax": Wmax,
                "Size": Sz,
                "Dims": Dims,
                "Spacing": Sp,
                "Origin": Origin,
                "Direction": Direction,
                "TransformMatrix": TransformMatrix,
                "DirectionMatrix_4x4": DirectionMatrix_4x4,
                "TransMatrix_4x4": TransMatrix_4x4,
                "VtkTransform_4x4": VtkTransform_4x4,
                "VolumeCenter": VCenter,
            }

            tags = {
                "StudyDate": "0008|0020",
                "PatientName": "0010|0010",
                "PatientID": "0010|0020",
                "BirthDate": "0010|0030",
                "WinCenter": "0028|1050",
                "WinWidth": "0028|1051",
            }
            for k, tag in tags.items():
                if tag in Image3D.GetMetaDataKeys():
                    v = Image3D.GetMetaData(tag)
                    DcmInfo[k] = v
                else:
                    v = ""

                DcmInfo[k] = v
                Image3D.SetMetaData(tag, v)

            # Set DcmInfo property :
            BDENTAL_Props.DcmInfo = str(DcmInfo)

            #######################################################################################
            # Add directories :
            SlicesDir = os.path.join(UserProjectDir, "Slices")
            if not os.path.exists(SlicesDir):
                os.makedirs(SlicesDir)
            BDENTAL_Props.SlicesDir = SlicesDir

            PngDir = os.path.join(UserProjectDir, "PNG")
            if not os.path.exists(PngDir):
                os.makedirs(PngDir)
            BDENTAL_Props.PngDir = PngDir

            PatientName = DcmInfo["PatientName"]
            PatientID = DcmInfo["PatientID"]
            Preffix = PatientName or PatientID
            if Preffix:
                # NrrdHuPath = os.path.join(UserProjectDir, f"{Preffix}_Image3DHu.nrrd")
                Nrrd255Path = os.path.join(UserProjectDir, f"{Preffix}_Image3D255.nrrd")
            else:
                # NrrdHuPath = os.path.join(UserProjectDir, "Image3DHu.nrrd")
                Nrrd255Path = os.path.join(UserProjectDir, "Image3D255.nrrd")
            # BDENTAL_Props.NrrdHuPath = NrrdHuPath
            BDENTAL_Props.Nrrd255Path = Nrrd255Path

            #######################################################################################
            # set IntensityWindowing  :
            Image3D_255 = sitk.Cast(
                sitk.IntensityWindowing(
                    Image3D,
                    windowMinimum=Wmin,
                    windowMaximum=Wmax,
                    outputMinimum=0.0,
                    outputMaximum=255.0,
                ),
                sitk.sitkUInt8,
            )

            # Convert Dicom to nrrd file :
            # sitk.WriteImage(Image3D, NrrdHuPath)
            sitk.WriteImage(Image3D_255, Nrrd255Path)

            #############################################################################################
            # MultiThreading PNG Writer:
            #########################################################################################
            def Image3DToPNG(i, slices, PngDir):
                img_Slice = slices[i]
                img_Name = "img_{0:04d}.png".format(i)
                img_Out = os.path.join(PngDir, img_Name)
                cv2.imwrite(img_Out, img_Slice)
                # sitk.WriteImage(img_Slice, img_Out)
                print(f"{img_Name} was processed...")

            #########################################################################################
            # Get slices list :
            Array = sitk.GetArrayFromImage(Image3D_255)
            slices = [np.flipud(Array[i, :, :]) for i in range(Array.shape[0])]
            # slices = [Image3D_255[:, :, i] for i in range(Image3D_255.GetDepth())]
            threads = [
                threading.Thread(
                    target=Image3DToPNG,
                    args=[i, slices, PngDir],
                    daemon=True,
                )
                for i in range(len(slices))
            ]

            for t in threads:
                t.start()

            for t in threads:
                t.join()
            if Preffix:
                BlendFile = f"{Preffix}SCAN.blend"
            else:
                BlendFile = "SCAN.blend"
            Blendpath = os.path.join(BDENTAL_Props.UserProjectDir, BlendFile)
            bpy.ops.wm.save_as_mainfile(filepath=Blendpath)

            #############################################################################################
            finish = time.perf_counter()
            print(f"OPEN SCAN FINISHED in {finish-start} second(s)")
            #############################################################################################

            return {"FINISHED"}


##########################################################################################
######################### BDENTAL Volume Render : ########################################
##########################################################################################
class BDENTAL_OT_Volume_Render(bpy.types.Operator):
    """ Volume Render """

    bl_idname = "bdental.volume_render"
    bl_label = "RENDER VOLUME"

    def execute(self, context):

        global ShadersBlendFile
        global GpShader

        BDENTAL_Props = context.scene.BDENTAL_Props
        Wmin = BDENTAL_Props.Wmin
        Wmax = BDENTAL_Props.Wmax
        DcmInfo = eval(BDENTAL_Props.DcmInfo)
        PngDir = BDENTAL_Props.PngDir
        CTVolumeList = [
            obj for obj in context.scene.objects if obj.name.endswith("CTVolume")
        ]

        if CTVolumeList == []:

            VolumeRender(DcmInfo, PngDir, GpShader, ShadersBlendFile)
            scn = bpy.context.scene
            scn.render.engine = "BLENDER_EEVEE"
            BDENTAL_Props.GroupNodeName = GpShader

            if GpShader == "VGS_Marcos_modified":
                GpNode = bpy.data.node_groups[GpShader]
                Low_Treshold = GpNode.nodes["Low_Treshold"].outputs[0]
                GpNode.nodes["WminNode"].outputs[0].default_value = Wmin
                WmaxNode = GpNode.nodes["WmaxNode"].outputs[0].default_value = Wmax

                newdriver = Low_Treshold.driver_add("default_value")
                newdriver.driver.type = "AVERAGE"
                var = newdriver.driver.variables.new()
                var.name = "Treshold"
                var.type = "SINGLE_PROP"
                var.targets[0].id_type = "SCENE"
                var.targets[0].id = bpy.context.scene
                var.targets[0].data_path = "BDENTAL_Props.Treshold"

                Wmin = BDENTAL_Props.Wmin
                Wmax = BDENTAL_Props.Wmax

                newdriver.driver.expression = "Treshold"

            if GpShader == "VGS_Dakir_01":
                # Add Treshold Driver :
                GpNode = bpy.data.node_groups[GpShader]
                treshramp = GpNode.nodes["TresholdRamp"].color_ramp.elements[0]
                newdriver = treshramp.driver_add("position")
                newdriver.driver.type = "SCRIPTED"
                var = newdriver.driver.variables.new()
                var.name = "Treshold"
                var.type = "SINGLE_PROP"
                var.targets[0].id_type = "SCENE"
                var.targets[0].id = bpy.context.scene
                var.targets[0].data_path = "BDENTAL_Props.Treshold"
                newdriver.driver.expression = f"(Treshold-{Wmin})/{Wmax-Wmin}"

            BDENTAL_Props.CT_Rendered = True
            PatientName = DcmInfo["PatientName"]
            PatientID = DcmInfo["PatientID"]
            Preffix = PatientName or PatientID
            if Preffix:
                BlendFile = f"{Preffix}SCAN.blend"
            else:
                BlendFile = "SCAN.blend"
            Blendpath = os.path.join(BDENTAL_Props.UserProjectDir, BlendFile)
            bpy.ops.wm.save_as_mainfile(filepath=Blendpath)
            bpy.ops.view3d.view_selected(use_all_regions=False)

            return {"FINISHED"}

        else:
            message = "Please delete, or change name of previously rendered volumes and retry !"
            ShowMessageBox(message=message, icon="COLORSET_01_VEC")
            return {"CANCELLED"}


##########################################################################################
######################### BDENTAL Add Slices : ########################################
##########################################################################################


class BDENTAL_OT_AddSlices(bpy.types.Operator):
    """ Add Volume Slices """

    bl_idname = "bdental.addslices"
    bl_label = "SLICE VOLUME"

    def execute(self, context):
        AddAxialSlice()
        obj = bpy.context.object
        MoveToCollection(obj=obj, CollName="SLICES")
        AddCoronalSlice()
        obj = bpy.context.object
        MoveToCollection(obj=obj, CollName="SLICES")
        AddSagitalSlice()
        obj = bpy.context.object
        MoveToCollection(obj=obj, CollName="SLICES")
        return {"FINISHED"}


###############################################################################
####################### BDENTAL VOLUME to Mesh : ################################
##############################################################################
class BDENTAL_OT_TreshSegment(bpy.types.Operator):
    """ Add a mesh Segmentation using Treshold """

    bl_idname = "bdental.tresh_segment"
    bl_label = "SEGMENTATION"

    SegmentName: StringProperty(
        name="Segmentation Name",
        default="TEST",
        description="Segmentation Name",
    )
    SegmentColor: FloatVectorProperty(
        name="Segmentation Color",
        description="Segmentation Color",
        default=[0.44, 0.4, 0.5, 1.0],  # (0.8, 0.46, 0.4, 1.0),
        soft_min=0.0,
        soft_max=1.0,
        size=4,
        subtype="COLOR",
    )

    TimingDict = {}

    def invoke(self, context, event):
        BDENTAL_Props = bpy.context.scene.BDENTAL_Props
        Wmin = BDENTAL_Props.Wmin
        Wmax = BDENTAL_Props.Wmax
        Nrrd255Path = BDENTAL_Props.Nrrd255Path
        Treshold = BDENTAL_Props.Treshold
        if os.path.exists(Nrrd255Path):
            if GpShader == "VGS_Marcos_modified":
                GpNode = bpy.data.node_groups[GpShader]
                ColorPresetRamp = GpNode.nodes["ColorPresetRamp"].color_ramp
                value = (Treshold - Wmin) / (Wmax - Wmin)
                TreshColor = [round(c, 2) for c in ColorPresetRamp.evaluate(value)[0:3]]
                self.SegmentColor = TreshColor + [1.0]
            self.q = Queue()
            wm = context.window_manager
            return wm.invoke_props_dialog(self)

        else:
            message = " Image File not Found in Project Folder ! "
            ShowMessageBox(message=message, icon="COLORSET_01_VEC")
            return {"CANCELLED"}

    def DicomToMesh(self):
        counter_start = counter()
        # Load Infos :
        #########################################################################
        BDENTAL_Props = bpy.context.scene.BDENTAL_Props
        # NrrdHuPath = BDENTAL_Props.NrrdHuPath
        Nrrd255Path = BDENTAL_Props.Nrrd255Path
        UserProjectDir = BDENTAL_Props.UserProjectDir
        DcmInfo = eval(BDENTAL_Props.DcmInfo)
        Origin = DcmInfo["Origin"]
        VtkTransform_4x4 = DcmInfo["VtkTransform_4x4"]
        VtkMatrix = list(np.array(VtkTransform_4x4).ravel())
        Treshold = BDENTAL_Props.Treshold

        Wmin = BDENTAL_Props.Wmin
        Wmax = BDENTAL_Props.Wmax
        StlPath = os.path.join(UserProjectDir, f"{self.SegmentName}_SEGMENTATION.stl")
        Thikness = 1
        # Reduction = 0.9
        SmoothIterations = SmthIter = 5

        ############### step 1 : Reading DICOM #########################
        self.q.put(["GuessTime", "PROGRESS : Reading DICOM...", "", 0, 0.1, 1])

        Image3D = sitk.ReadImage(Nrrd255Path)
        Sz = Image3D.GetSize()
        Sp = Image3D.GetSpacing()
        MaxSp = max(Vector(Sp))
        if MaxSp < 0.25:
            SampleRatio = round(MaxSp / 0.25, 2)
            ResizedImage = ResizeImage(sitkImage=Image3D, Ratio=SampleRatio)
            Image3D = ResizedImage
            # print(f"Image DOWN Sampled : SampleRatio = {SampleRatio}")

        # Convert Hu treshold value to 0-255 UINT8 :
        Treshold255 = HuTo255(Hu=Treshold, Wmin=Wmin, Wmax=Wmax)
        if Treshold255 == 0:
            Treshold255 = 1
        elif Treshold255 == 255:
            Treshold255 = 254

        step1 = counter()
        self.TimingDict["Read DICOM"] = step1 - counter_start
        # print(f"step 1 : Read DICOM ({step1-start})")

        ############### step 2 : Extracting mesh... #########################
        self.q.put(["GuessTime", "PROGRESS : Extracting mesh...", "", 0.1, 0.2, 2])

        # print("Extracting mesh...")
        vtkImage = sitkTovtk(sitkImage=Image3D)

        ExtractedMesh = vtk_MC_Func(vtkImage=vtkImage, Treshold=Treshold255)
        Mesh = ExtractedMesh

        polysCount = Mesh.GetNumberOfPolys()
        polysLimit = 800000

        # step1 = time.perf_counter()
        # print(f"before reduction finished in : {step1-start} secondes")
        step2 = counter()
        self.TimingDict["extract mesh"] = step2 - step1
        # print(f"step 2 : extract mesh ({step2-step1})")

        ############### step 3 : mesh Reduction... #########################
        if polysCount > polysLimit:
            # print(f"Hight polygons count, : ({polysCount}) Mesh will be reduced...")
            Reduction = round(1 - (polysLimit / polysCount), 2)
            # print(f"MESH REDUCTION: Ratio = ({Reduction}) ...")
            ReductedMesh = vtkMeshReduction(
                q=self.q,
                mesh=Mesh,
                reduction=Reduction,
                step="Mesh Reduction",
                start=0.2,
                finish=0.5,
            )
            Mesh = ReductedMesh
            # print(f"Reduced Mesh polygons count : {Mesh.GetNumberOfPolys()} ...")
            # step2 = time.perf_counter()
            # print(f"reduction finished in : {step2-step1} secondes")
        # else:
        # print(f"Original mesh polygons count is Optimal : ({polysCount})...")
        step3 = counter()
        self.TimingDict["Reduct mesh"] = step3 - step2
        # print(f"step 3 : Reduct mesh ({step3-step2})")

        ############### step 4 : mesh Smoothing... #########################
        # print("SMOOTHING...")
        SmoothedMesh = vtkSmoothMesh(
            q=self.q,
            mesh=Mesh,
            Iterations=SmthIter,
            step="Mesh Orientation",
            start=0.5,
            finish=0.6,
        )
        step3 = counter()
        # try:
        #     print(f"SMOOTHING finished in : {step3-step2} secondes...")
        # except Exception:
        #     print(f"SMOOTHING finished in : {step3-step1} secondes (no Reduction!)...")
        step4 = counter()
        self.TimingDict["Smooth mesh"] = step4 - step3
        # print(f"step 4 : Smooth mesh ({step4-step3})")

        ############### step 5 : Set mesh orientation... #########################
        # print("SET MESH ORIENTATION...")
        TransformedMesh = vtkTransformMesh(
            mesh=SmoothedMesh,
            Matrix=VtkMatrix,
        )
        step5 = counter()
        self.TimingDict["Mesh Transform"] = step5 - step4
        # print(f"step 5 : set mesh orientation({step5-step4})")

        ############### step 6 : exporting mesh stl... #########################
        self.q.put(
            [
                "GuessTime",
                "PROGRESS : exporting mesh stl...",
                "",
                0.6,
                0.7,
                2,
            ]
        )

        # print("WRITING...")
        writer = vtk.vtkSTLWriter()
        writer.SetInputData(TransformedMesh)
        writer.SetFileTypeToBinary()
        writer.SetFileName(StlPath)
        writer.Write()

        # step4 = time.perf_counter()
        # print(f"WRITING finished in : {step4-step3} secondes")
        step6 = counter()
        self.TimingDict["Export mesh"] = step6 - step5
        # print(f"step 6 : Export mesh ({step6-step5})")

        ############### step 7 : Importing mesh to Blender... #########################
        self.q.put(["GuessTime", "PROGRESS : Importing mesh...", "", 0.7, 0.9, 10])

        # print("IMPORTING...")
        # import stl to blender scene :
        bpy.ops.import_mesh.stl(filepath=StlPath)
        obj = bpy.context.object
        obj.name = f"{self.SegmentName}_SEGMENTATION"
        obj.data.name = f"{self.SegmentName}_mesh"

        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

        step7 = counter()
        self.TimingDict["Import mesh"] = step7 - step6
        # print(f"step 7 : Import mesh({step7-step6})")
        ############### step 8 : Add material... #########################
        self.q.put(["GuessTime", "PROGRESS : Add material...", "", 0.9, 0.95, 2])

        # print("ADD COLOR MATERIAL")
        mat = bpy.data.materials.get(obj.name) or bpy.data.materials.new(obj.name)
        mat.diffuse_color = self.SegmentColor
        obj.data.materials.append(mat)
        MoveToCollection(obj=obj, CollName="SEGMENTS")
        bpy.ops.object.shade_smooth()

        bpy.ops.object.modifier_add(type="CORRECTIVE_SMOOTH")
        bpy.context.object.modifiers["CorrectiveSmooth"].iterations = 3
        bpy.context.object.modifiers["CorrectiveSmooth"].use_only_smooth = True

        # step5 = time.perf_counter()
        # print(f"Blender importing finished in : {step5-step4} secondes")

        step8 = counter()
        self.TimingDict["Add material"] = step8 - step7
        # print(f"step 8 : Add material({step8-step7})")

        self.q.put(["End"])
        counter_finish = counter()
        self.TimingDict["Total Time"] = counter_finish - counter_start

    def execute(self, context):
        counter_start = counter()
        TerminalProgressBar = BDENTAL_Utils.TerminalProgressBar
        CV2_progress_bar = BDENTAL_Utils.CV2_progress_bar
        self.t1 = threading.Thread(
            target=TerminalProgressBar, args=[self.q, counter_start], daemon=True
        )
        self.t2 = threading.Thread(target=CV2_progress_bar, args=[self.q], daemon=True)

        # self.t1.start()
        self.t2.start()
        self.DicomToMesh()
        # self.t1.join()
        self.t2.join()
        # print("\n")
        # print(self.TimingDict)

        return {"FINISHED"}


#################################################################################################
# Registration :
#################################################################################################

classes = [
    BDENTAL_OT_Load_DICOM_Series,
    BDENTAL_OT_Load_3DImage_File,
    BDENTAL_OT_Volume_Render,
    BDENTAL_OT_AddSlices,
    BDENTAL_OT_TreshSegment,
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
