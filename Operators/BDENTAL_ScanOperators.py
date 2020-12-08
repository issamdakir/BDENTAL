# Python imports :
import time, os, sys, shutil, math, threading
from math import degrees, radians, pi
import numpy as np

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


# import BDENTAL_Utils Functions :
from .BDENTAL_Utils import *

# Global variables :
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ShadersBlendFile = os.path.join(
    addon_dir, "Resources\BlendData\BDENTAL_Shaders_collection.blend"
)
GpShader = "VGS_06"
Wmin = -400
Wmax = 3000

#######################################################################################
########################### CT Scan Load : Operators ##############################
#######################################################################################
# BDENTAL CT Scan Series Load :
class BDENTAL_OT_Load_DICOM_Series(bpy.types.Operator):
    """ Load scan infos """

    bl_idname = "bdental.load_dicom_series"
    bl_label = "OPEN SCAN"

    def execute(self, context):

        ################################################################################################
        print("processing START...")
        start = time.perf_counter()
        ################################################################################################

        BDENTAL_Props = context.scene.BDENTAL_Props
        UserDcmDir = BDENTAL_Props.UserDcmDir
        UserProjectDir = BDENTAL_Props.UserProjectDir

        ################################################################################################

        if not os.path.exists(UserProjectDir):

            message = "The Selected Project Directory Path is not valid ! "
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")
            return {"CANCELLED"}

        if os.listdir(UserProjectDir):

            message = " Project Folder Should be Empty ! "
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")
            return {"CANCELLED"}

        elif not os.path.exists(UserDcmDir):

            message = " Please use the Folder icon to Select a valid Dicom Directory ! "
            ShowMessageBox(message=message, icon="COLORSET_02_VEC")
            return {"CANCELLED"}

        else:

            DcmSerie = []

            # ensure is .dcm sequence
            f_list = [
                os.path.join(UserDcmDir, f)
                for f in os.listdir(UserDcmDir)
                if os.path.isfile(os.path.join(UserDcmDir, f))
            ]
            if not f_list or len(f_list) == 1:

                message = "No valid DICOM Serie found in DICOM Folder ! "
                ShowMessageBox(message=message, icon="COLORSET_02_VEC")
                return {"CANCELLED"}

            if len(f_list) > 1:

                Series_reader = sitk.ImageSeriesReader()
                series_IDs = Series_reader.GetGDCMSeriesIDs(UserDcmDir)

                if not series_IDs:

                    print("No valid DICOM Serie found in DICOM Folder ! ")
                    message = "No valid DICOM Serie found in DICOM Folder ! "
                    ShowMessageBox(message=message, icon="COLORSET_01_VEC")
                    return {"CANCELLED"}

                if len(series_IDs) == 1:
                    DcmSerie = Series_reader.GetGDCMSeriesFileNames(
                        UserDcmDir, series_IDs[0]
                    )

                if len(series_IDs) > 1:
                    unsorted_SeriesID = {}
                    sorted_SeriesID = []

                    for sID in series_IDs:
                        dcm_sequence = Series_reader.GetGDCMSeriesFileNames(
                            UserDcmDir, sID
                        )
                        key = sID
                        value = (len(dcm_sequence), dcm_sequence)
                        unsorted_SeriesID[key] = value

                    for key, value in sorted(
                        unsorted_SeriesID.items(),
                        key=lambda item: item[1][0],
                        reverse=True,
                    ):
                        sorted_SeriesID.append(value[1])

                    DcmSerie = list(sorted_SeriesID[0])

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

            Wmin = BDENTAL_Props.Wmin
            Wmax = BDENTAL_Props.Wmax

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
        default=(0.8, 0.46, 0.4, 1.0),
        soft_min=0.0,
        soft_max=1.0,
        size=4,
        subtype="COLOR",
    )

    def invoke(self, context, event):
        BDENTAL_Props = bpy.context.scene.BDENTAL_Props
        # NrrdHuPath = BDENTAL_Props.NrrdHuPath
        Nrrd255Path = BDENTAL_Props.Nrrd255Path
        if os.path.exists(Nrrd255Path):
            wm = context.window_manager
            return wm.invoke_props_dialog(self)

        else:
            message = " Image File not Found in Project Folder ! "
            ShowMessageBox(message=message, icon="COLORSET_01_VEC")
            return {"CANCELLED"}

    def execute(self, context):

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
        SegmentName = self.SegmentName
        SegmentColor = self.SegmentColor
        StlPath = os.path.join(UserProjectDir, f"{SegmentName}_SEGMENTATION.stl")
        Thikness = 1
        # Reduction = 0.9
        SmoothIterations = SmthIter = 3
        #########################################################################
        start = time.perf_counter()

        Image3D = sitk.ReadImage(Nrrd255Path)
        Sz = Image3D.GetSize()
        OriginalSize = Sz[0] * Sz[1] * Sz[2]
        if OriginalSize > 100000000:
            SampleRatio = 100000000 / OriginalSize
            ResizedImage = ResizeImage(sitkImage=Image3D, Ratio=SampleRatio)
            Image3D = ResizedImage
            print(f"Image DOWN Sampled : SampleRatio = {SampleRatio}")
        print("CONVERTING IMAGE...")
        vtkImage = sitkTovtk(sitkImage=Image3D)

        print("EXTRACTING Mesh...")
        Treshold255 = HuTo255(Hu=Treshold, Wmin=Wmin, Wmax=Wmax)
        if Treshold255 == 0:
            Treshold255 = 1
        elif Treshold255 == 255:
            Treshold255 = 254
        ExtractedMesh = vtk_MC_Func(vtkImage=vtkImage, Treshold=Treshold255)
        polysCount = ExtractedMesh.GetNumberOfPolys()
        print(f"ExtractedMesh polygons count : {polysCount} ...")

        Reduction = 0.0
        polysLimit = 250000
        if polysCount > polysLimit:
            Reduction = round(1 - (polysLimit / polysCount), 2)

        print(f"MESH REDUCTION: Ratio = {Reduction}...")
        ReductedMesh = vtkMeshReduction(mesh=ExtractedMesh, reduction=Reduction)
        print(f"ReductedMesh polygons count : {ReductedMesh.GetNumberOfPolys()} ...")

        # print("SMOOTHING...")
        # SmoothedMesh = vtkSmoothMesh(mesh=ReductedMesh, Iterations=SmthIter)
        # print(f"SmoothedMesh polygons count : {SmoothedMesh.GetNumberOfPolys()} ...")

        print("SET MESH ORIENTATION...")
        TransformedMesh = vtkTransformMesh(mesh=ReductedMesh, Matrix=VtkMatrix)

        print("WRITING...")
        writer = vtk.vtkSTLWriter()
        writer.SetInputData(TransformedMesh)
        writer.SetFileTypeToBinary()
        writer.SetFileName(StlPath)
        writer.Write()

        print("IMPORTING...")
        # import stl to blender scene :
        bpy.ops.import_mesh.stl(filepath=StlPath)
        obj = bpy.context.object
        obj.name = f"{SegmentName}_SEGMENTATION"
        obj.data.name = f"{SegmentName}_mesh"

        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

        print("ADD COLOR MATERIAL")
        mat = bpy.data.materials.get(obj.name) or bpy.data.materials.new(obj.name)
        mat.diffuse_color = SegmentColor
        obj.data.materials.append(mat)
        MoveToCollection(obj=obj, CollName="SEGMENTS")

        bpy.ops.object.modifier_add(type="CORRECTIVE_SMOOTH")
        bpy.context.object.modifiers["CorrectiveSmooth"].iterations = 3
        bpy.context.object.modifiers["CorrectiveSmooth"].use_only_smooth = True

        finish = time.perf_counter()
        print(f"FINISHED in {finish-start} secondes")

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
