# Python imports :
import time, os, sys, shutil, math, threading
from math import degrees, radians, pi
import numpy as np

# Blender Imports :
import bpy
import bmesh
from mathutils import Matrix, Vector, Euler, kdtree

requirements = R"C:\MyPythonResources\Requirements"
if not requirements in sys.path:
    sys.path.append(requirements)
import SimpleITK as sitk
import cv2

# import BDENTAL_Utils Functions :
from . import BDENTAL_Utils

# Global variables :
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ShadersBlendFile = os.path.join(
    addon_dir, "Resources\BlendData\BDENTAL_Shaders_collection.blend"
)
GpShader = "VGS_06"
Wmin = -400
Wmax = 3000
# Load functions :
ShowMessageBox = BDENTAL_Utils.ShowMessageBox
MoveToCollection = BDENTAL_Utils.MoveToCollection  # args : (obj, CollName)
Scene_Settings = BDENTAL_Utils.Scene_Settings

#######################################################################################
########################### CT Scan Load : Operators ##############################
#######################################################################################
# BFD CT Scan Series Load
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
                and f.endswith((".dcm", ".DCM"))
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

            # # Change Origin and direction:
            # Origin = Ortho_Origin = -0.5 * (np.array(Sp) * np.array(Sz))
            # Direction =  Identity = (1, 0, 0, 0, 1, 0, 0, 0, 1)
            # Image3D.SetOrigin(Origin)
            # Image3D.SetDirection(Direction)

            # calculate the center of the volume :
            P0 = Image3D.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
            P_diagonal = Image3D.TransformContinuousIndexToPhysicalPoint(
                (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
            )
            VCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5

            C = VCenter
            D = Direction
            TransformMatrix = Matrix(
                (
                    (D[0], D[1], D[2], C[0]),
                    (D[3], D[4], D[5], C[1]),
                    (D[6], D[7], D[8], C[2]),
                    (0.0, 0.0, 0.0, 1),
                )
            )
            DirectionMatrix = Matrix(
                ((D[0], D[1], D[2]), (D[3], D[4], D[5]), (D[6], D[7], D[8]))
            )

            # Set DcmInfo :

            BDENTAL_Props.Wmin = Wmin
            BDENTAL_Props.Wmax = Wmax

            DcmInfo = {
                "PixelType": Image3D.GetPixelIDTypeAsString(),
                "wmin": Wmin,
                "wmax": Wmax,
                "size": Sz,
                "dims": Dims,
                "spacing": Sp,
                "Origin": Origin,
                "direction": Direction,
                "TransformMatrix": TransformMatrix,
                "DirectionMatrix": DirectionMatrix,
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
                NrrdImagePath = os.path.join(UserProjectDir, f"{Preffix}_Image3D.nrrd")
            else:
                NrrdImagePath = os.path.join(UserProjectDir, "Image3D.nrrd")
            BDENTAL_Props.NrrdImagePath = NrrdImagePath

            #######################################################################################
            if DcmInfo["PixelType"] == "8-bit unsigned integer":
                Image3D_255 = Image3D
            else:

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
            sitk.WriteImage(Image3D_255, NrrdImagePath)

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

            #############################################################################################
            finish = time.perf_counter()
            print(f"OPEN SCAN FINISHED in {finish-start} second(s)")
            #############################################################################################

            return {"FINISHED"}


#######################################################################################
# BFD CT Scan 3DImage File Load
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
            message = " Please use the Folder icon to Select a valid Image File ! "
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

        ###########################################################################################################

        else:

            print("processing START...")
            start = time.perf_counter()
            ###################################################################################
            # Get Dicom Info :
            Sp = Spacing = Image3D.GetSpacing()
            Sz = Size = Image3D.GetSize()
            Dims = Dimensions = Image3D.GetDimension()
            Origin = Image3D.GetOrigin()
            Direction = Image3D.GetDirection()

            # # Change Origin and direction:
            # Origin = Ortho_Origin = -0.5 * (np.array(Sp) * np.array(Sz))
            # Direction =  Identity = (1, 0, 0, 0, 1, 0, 0, 0, 1)
            # Image3D.SetOrigin(Origin)
            # Image3D.SetDirection(Direction)

            # calculate the center of the volume :
            P0 = Image3D.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
            P_diagonal = Image3D.TransformContinuousIndexToPhysicalPoint(
                (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
            )
            VCenter = (P0 + P_diagonal) * 0.5

            C = VCenter
            D = Direction
            TransformMatrix = Matrix(
                (
                    (D[0], D[3], D[6], C[0]),
                    (D[1], D[4], D[7], C[1]),
                    (D[2], D[5], D[8], C[2]),
                    (0.0, 0.0, 0.0, 1),
                )
            )
            DirectionMatrix = Matrix(
                ((D[0], D[3], D[6]), (D[1], D[4], D[7]), (D[2], D[5], D[8]))
            )

            # Set DcmInfo :
            BDENTAL_Props.Wmin = Wmin
            BDENTAL_Props.Wmax = Wmax
            DcmInfo = {
                "PixelType": Image3D.GetPixelIDTypeAsString(),
                "wmin": Wmin,
                "wmax": Wmax,
                "size": Sz,
                "dims": Dims,
                "spacing": Sp,
                "Origin": Origin,
                "direction": Direction,
                "TransformMatrix": TransformMatrix,
                "DirectionMatrix": DirectionMatrix,
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
                NrrdImagePath = os.path.join(UserProjectDir, f"{Preffix}_Image3D.nrrd")
            else:
                NrrdImagePath = os.path.join(UserProjectDir, "Image3D.nrrd")

            BDENTAL_Props.NrrdImagePath = NrrdImagePath

            #######################################################################################
            if DcmInfo["PixelType"] == "8-bit unsigned integer":
                Image3D_255 = Image3D
            else:
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
            sitk.WriteImage(Image3D_255, NrrdImagePath)

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

            #############################################################################################
            finish = time.perf_counter()
            print(f"OPEN SCAN FINISHED in {finish-start} second(s)")
            #############################################################################################

            return {"FINISHED"}


##########################################################################################
# Volume Render
##########################################################################################
def AddBooleanCube(DimX, DimY, DimZ):
    bpy.ops.mesh.primitive_cube_add(
        size=max(DimX, DimY, DimZ) * 1.5,
        enter_editmode=False,
        align="WORLD",
        location=(0, 0, 0),
        scale=(1, 1, 1),
    )

    VOI = VolumeOfInterst = bpy.context.object
    VOI.name = "VOI"
    VOI.display_type = "WIRE"
    return VOI


def AddNode(nodes, type, name):

    node = nodes.new(type)
    node.name = name
    # node.location[0] -= 200

    return node


def VolumeRender(DcmInfo, PngDir, GpShader, ShadersBlendFile):
    #################################################################################
    Start = time.perf_counter()
    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    # acctivate io_import_images_as_planes :
    bpy.ops.preferences.addon_enable(module="io_import_images_as_planes")
    # Set Render settings :
    Scene_Settings()

    os.chdir(PngDir)
    ImagesList = sorted(os.listdir(PngDir))

    Sp = Spacing = DcmInfo["spacing"]
    Sz = Size = DcmInfo["size"]
    Origin = DcmInfo["Origin"]
    Direction = DcmInfo["direction"]
    TransformMatrix = DcmInfo["TransformMatrix"]
    DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
    Offset = Sp[2]

    ###############################################################################################
    # Add Planes with textured material :
    PlansList = []

    for i, ImagePNG in enumerate(ImagesList):
        bpy.ops.import_image.to_plane(
            files=[{"name": ImagePNG, "name": ImagePNG}],
            directory=PngDir,
            align_axis="Z+",
            relative=False,
            height=DimY,
        )

        bpy.ops.transform.translate(
            value=(0, 0, Offset * i), constraint_axis=(False, False, True)
        )
        objName = ImagePNG.split(".")[0]
        obj = bpy.data.objects[objName]
        PlansList.append(obj)
        print(f"{ImagePNG} Processed ...")
        # Add Material :
        mat = bpy.data.materials.new(f"Voxelmat_{i}")
        mat.use_nodes = True
        node_tree = mat.node_tree
        nodes = node_tree.nodes
        links = node_tree.links

        for node in nodes:
            if node.type != "OUTPUT_MATERIAL":
                nodes.remove(node)

        image_path = os.path.join(PngDir, ImagePNG)
        ImageData = bpy.data.images.get(ImagePNG)
        TextureCoord = AddNode(nodes, type="ShaderNodeTexCoord", name="TextureCoord")
        ImageTexture = AddNode(nodes, type="ShaderNodeTexImage", name="Image Texture")
        ImageTexture.image = ImageData
        ImageData.colorspace_settings.name = "Non-Color"

        materialOutput = nodes["Material Output"]

        links.new(TextureCoord.outputs[0], ImageTexture.inputs[0])

        # Load VGS Group Node :
        VGS = bpy.data.node_groups.get(GpShader)
        if not VGS:
            filepath = os.path.join(ShadersBlendFile, f"NodeTree\{GpShader}")
            directory = os.path.join(ShadersBlendFile, "NodeTree")
            filename = GpShader
            bpy.ops.wm.append(filepath=filepath, filename=filename, directory=directory)
            VGS = bpy.data.node_groups.get(GpShader)

        GroupNode = nodes.new("ShaderNodeGroup")
        GroupNode.node_tree = VGS

        links.new(ImageTexture.outputs["Color"], GroupNode.inputs[0])
        links.new(GroupNode.outputs[0], materialOutput.inputs["Surface"])
        for slot in obj.material_slots:
            bpy.ops.object.material_slot_remove()

        bpy.ops.object.material_slot_add()

        obj.active_material = mat

        mat.blend_method = "HASHED"
        mat.shadow_method = "HASHED"

        # move obj to COLLECTION : "CT_Scan Voxel"
        MoveToCollection(obj, CollName="CT Voxel")

        bpy.context.view_layer.update()

    # Join Planes Make Cube Voxel :
    bpy.ops.object.select_all(action="DESELECT")
    for obj in PlansList:
        MoveToCollection(obj, CollName="CT Voxel")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    bpy.ops.object.join()

    Voxel = bpy.context.object
    PatientName = DcmInfo["PatientName"]
    PatientID = DcmInfo["PatientID"]
    Preffix = PatientName or PatientID
    if Preffix:
        Voxel.name = f"{Preffix}_CTVolume"
    else:
        Voxel.name = "CTVolume"

    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

    Voxel.matrix_world = DcmInfo["TransformMatrix"]

    # Change to ORTHO persp with nice view angle :
    ViewMatrix = Matrix(
        (
            (0.8435, -0.5371, -0.0000, 1.2269),
            (0.2497, 0.3923, 0.8853, -15.1467),
            (-0.4755, -0.7468, 0.4650, -55.2801),
            (0.0000, 0.0000, 0.0000, 1.0000),
        )
    )

    bpy.ops.file.pack_all()
    bpy.ops.object.select_all(action="DESELECT")

    for scr in bpy.data.screens:
        # if scr.name in ["Layout", "Scripting", "Shading"]:
        for area in [ar for ar in scr.areas if ar.type == "VIEW_3D"]:
            for space in [sp for sp in area.spaces if sp.type == "VIEW_3D"]:
                r3d = space.region_3d
                r3d.view_perspective = "ORTHO"
                r3d.view_distance = 150
                r3d.view_matrix = ViewMatrix
                r3d.update()
                # space.show_region_ui = False
                space.shading.type = "MATERIAL"

    for i in range(3):
        Voxel.lock_location[i] = True
        Voxel.lock_rotation[i] = True
        Voxel.lock_scale[i] = True

    Finish = time.perf_counter()
    print(f"CT-Scan loaded in {Finish-Start} secondes")


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


#################################################################################################
# Add Slices :
#################################################################################################


def AxialSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = BDENTAL_Props.NrrdImagePath
    SlicesDir = BDENTAL_Props.SlicesDir
    DcmInfo = eval(BDENTAL_Props.DcmInfo)
    TransformMatrix = DcmInfo["TransformMatrix"]
    DirectionMatrix = DcmInfo["DirectionMatrix"]

    ImagePath = os.path.join(SlicesDir, "AXIAL.png")
    Plane = bpy.context.scene.objects["AXIAL"]

    if Plane and os.path.exists(ImageData):

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D.GetSpacing()
        Sz = Size = Image3D.GetSize()
        DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D.SetOrigin(Ortho_Origin)
        Image3D.SetDirection(np.identity(3).flatten())
        Origin = Image3D.GetOrigin()
        Direction = Image3D.GetDirection()
        P0 = Image3D.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
        P_diagonal = Image3D.TransformContinuousIndexToPhysicalPoint(
            (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
        )
        NewVCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5
        VC = VolumeCenter = DcmInfo["VolumeCenter"]

        # Output Parameters :
        Out_Origin = Vector([Origin[0], Origin[1], 0])
        Out_Direction = Vector(Direction)
        Out_Size = (Sz[0], Sz[1], 1)
        Out_Spacing = Sp

        ######################################
        # Get Plane Orientation and location :
        PlanMatrix = TransformMatrix.inverted() @ Plane.matrix_world
        Rot = PlanMatrix.to_euler()
        Trans = PlanMatrix.translation
        Rvec = (Rot.x, Rot.y, Rot.z)
        Tvec = Trans

        ##########################################
        # Euler3DTransform :
        Euler3D = sitk.Euler3DTransform()
        Euler3D.SetCenter(NewVCenter)
        Euler3D.SetRotation(Rvec[0], Rvec[1], Rvec[2])
        Euler3D.SetTranslation(Tvec)
        Euler3D.ComputeZYXOn()
        #########################################

        Image2D = sitk.Resample(
            Image3D,
            Out_Size,
            Euler3D,
            sitk.sitkLinear,
            Out_Origin,
            Out_Spacing,
            Out_Direction,
            100,
        )
        #############################################
        # Write Image :
        Array = sitk.GetArrayFromImage(Image2D)
        Flipped_Array = np.flipud(Array.reshape(Array.shape[1], Array.shape[2]))
        cv2.imwrite(ImagePath, Flipped_Array)
        #############################################
        # Update Blender Image data :
        BlenderImage = bpy.data.images.get("AXIAL.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("AXIAL.png")
        BlenderImage.reload()


####################################################################
def AddAxialSlice():

    name = "AXIAL"
    DcmInfo = eval(bpy.context.scene.BDENTAL_Props.DcmInfo)
    Sp, Sz, Origin, Direction = (
        DcmInfo["spacing"],
        DcmInfo["size"],
        DcmInfo["Origin"],
        DcmInfo["direction"],
    )

    DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])

    # Remove old Slices and their data meshs :
    OldSlices = [obj for obj in bpy.context.view_layer.objects if name in obj.name]
    OldSliceMeshs = [mesh for mesh in bpy.data.meshes if name in mesh.name]

    for obj in OldSlices:
        bpy.data.objects.remove(obj)
    for mesh in OldSliceMeshs:
        bpy.data.meshes.remove(mesh)

    # Add AXIAL :
    bpy.ops.mesh.primitive_plane_add()
    AxialPlane = bpy.context.active_object
    AxialPlane.name = name
    AxialPlane.data.name = f"{name}_mesh"
    AxialPlane.rotation_mode = "XYZ"
    AxialDims = (DimX, DimY, 0.0)
    AxialPlane.dimensions = AxialDims
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Add Material :
    mat = bpy.data.materials.get("AXIAL_mat") or bpy.data.materials.new("AXIAL_mat")

    for slot in AxialPlane.material_slots:
        bpy.ops.object.material_slot_remove()
    bpy.ops.object.material_slot_add()
    AxialPlane.active_material = mat

    mat.use_nodes = True
    node_tree = mat.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    for node in nodes:
        if node.type != "OUTPUT_MATERIAL":
            nodes.remove(node)
    SlicesDir = bpy.context.scene.BDENTAL_Props.SlicesDir
    ImageName = "AXIAL.png"
    ImagePath = os.path.join(SlicesDir, ImageName)

    # write "AXIAL.png" to here ImagePath
    AxialSliceUpdate(bpy.context.scene)

    BlenderImage = bpy.data.images.get(ImageName) or bpy.data.images.load(ImagePath)

    TextureCoord = AddNode(nodes, type="ShaderNodeTexCoord", name="TextureCoord")
    ImageTexture = AddNode(nodes, type="ShaderNodeTexImage", name="Image Texture")
    print(ImageTexture)
    ImageTexture.image = BlenderImage
    BlenderImage.colorspace_settings.name = "Non-Color"
    materialOutput = nodes["Material Output"]
    links.new(TextureCoord.outputs[0], ImageTexture.inputs[0])
    links.new(ImageTexture.outputs[0], materialOutput.inputs[0])
    bpy.context.scene.transform_orientation_slots[0].type = "LOCAL"
    bpy.context.scene.transform_orientation_slots[1].type = "LOCAL"
    bpy.ops.wm.tool_set_by_id(name="builtin.move")

    post_handlers = bpy.app.handlers.depsgraph_update_post
    [post_handlers.remove(h) for h in post_handlers if h.__name__ == "AxialSliceUpdate"]
    post_handlers.append(AxialSliceUpdate)


class BDENTAL_OT_AddSlices(bpy.types.Operator):
    """ Add Volume Slices """

    bl_idname = "bdental.addslices"
    bl_label = "SLICE VOLUME"

    def execute(self, context):
        AddAxialSlice()
        return {"FINISHED"}


#################################################################################################
# Registration :
#################################################################################################

classes = [
    BDENTAL_OT_Load_DICOM_Series,
    BDENTAL_OT_Load_3DImage_File,
    BDENTAL_OT_Volume_Render,
    BDENTAL_OT_AddSlices,
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
