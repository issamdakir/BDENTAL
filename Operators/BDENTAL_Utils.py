# # Python imports :

import time
import os
import sys
import shutil
import math
from math import degrees, radians, pi
import threading

requirements = R"C:\MyPythonResources\Requirements"
if not requirements in sys.path:
    sys.path.append(requirements)
import numpy as np
import SimpleITK as sitk
import cv2
import vtk
from vtk.util import numpy_support

# Blender Imports :
import bpy
import bmesh
from mathutils import Matrix, Vector, Euler, kdtree

# Global Variables :
addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#######################################################################################
# Popup message box function :
#######################################################################################


def ShowMessageBox(message="", title="INFO", icon="INFO"):
    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)


#######################################################################################
# Load CT Scan functions :
#######################################################################################

############################
# Make directory function :
############################
def make_directory(Root, DirName):

    DirPath = os.path.join(Root, DirName)
    if not DirName in os.listdir(Root):
        os.mkdir(DirPath)
    return DirPath


################################
# Copy DcmSerie To ProjDir function :
################################
def CopyDcmSerieToProjDir(DcmSerie, DicomSeqDir):
    for i in range(len(DcmSerie)):
        shutil.copy2(DcmSerie[i], DicomSeqDir)


##########################################################################################
######################### BDENTAL Volume Render : ########################################
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


def AddPlaneMesh(DimX, DimY, Name):
    x = DimX / 2
    y = DimY / 2
    verts = [(-x, -y, 0.0), (x, -y, 0.0), (-x, y, 0.0), (x, y, 0.0)]
    faces = [(0, 1, 3, 2)]
    mesh = bpy.data.meshes.new(f"{Name}_mesh")
    mesh.from_pydata(verts, [], faces)
    uvs = mesh.uv_layers.new(name=f"{Name}_uv")
    mesh.update()

    return mesh


def AddPlaneObject(Name, mesh, CollName):
    Plane_obj = bpy.data.objects.new(Name, mesh)
    Coll = bpy.data.collections.get(CollName)
    if not Coll:
        Coll = bpy.data.collections.new(CollName)
        bpy.context.scene.collection.children.link(Coll)
    if not Plane_obj in Coll.objects[:]:
        Coll.objects.link(Plane_obj)

    return Plane_obj


def VolumeRender(DcmInfo, PngDir, GpShader, ShadersBlendFile):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    Sp = Spacing = DcmInfo["Spacing"]
    Sz = Size = DcmInfo["Size"]
    Origin = DcmInfo["Origin"]
    Direction = DcmInfo["Direction"]
    TransformMatrix = DcmInfo["TransformMatrix"]
    DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
    Offset = Sp[2]
    ImagesList = sorted(os.listdir(PngDir))

    #################################################################################
    Start = time.perf_counter()
    #################################################################################
    # ///////////////////////////////////////////////////////////////////////////#
    ######################## Set Render settings : #############################
    Scene_Settings()
    ###################### Change to ORTHO persp with nice view angle :##########
    
    ViewMatrix = Matrix(
        (
            (0.8677, -0.4971, 0.0000, 4.0023),
            (0.4080, 0.7123, 0.5711, -14.1835),
            (-0.2839, -0.4956, 0.8209, -94.0148),
            (0.0000, 0.0000, 0.0000, 1.0000),
        )
    )
    for scr in bpy.data.screens:
        # if scr.name in ["Layout", "Scripting", "Shading"]:
        for area in [ar for ar in scr.areas if ar.type == "VIEW_3D"]:
            for space in [sp for sp in area.spaces if sp.type == "VIEW_3D"]:
                r3d = space.region_3d
                r3d.view_perspective = "ORTHO"
                r3d.view_distance = 320
                r3d.view_matrix = ViewMatrix
                r3d.update()

    ################### Load all PNG images : ###############################
    for ImagePNG in ImagesList:
        image_path = os.path.join(PngDir, ImagePNG)
        bpy.data.images.load(image_path)

    bpy.ops.file.pack_all()

    ###############################################################################################
    # Add Planes with textured material :
    ###############################################################################################
    PlansList = []
    ############################# START LOOP ##################################

    for i, ImagePNG in enumerate(ImagesList):
        # Add Plane :
        ##########################################
        Preffix = "PLANE_"
        Name = f"{Preffix}{i}"
        mesh = AddPlaneMesh(DimX, DimY, Name)
        CollName = "CT Voxel"

        obj = AddPlaneObject(Name, mesh, CollName)
        obj.location[2] = i * Offset
        PlansList.append(obj)
        ##########################################
        # Add Material :
        mat = bpy.data.materials.new(f"Voxelmat_{i}")
        mat.use_nodes = True
        node_tree = mat.node_tree
        nodes = node_tree.nodes
        links = node_tree.links

        for node in nodes:
            if node.type != "OUTPUT_MATERIAL":
                nodes.remove(node)

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

        obj.active_material = mat

        mat.blend_method = "HASHED"
        mat.shadow_method = "HASHED"

        print(f"{ImagePNG} Processed ...")
#         bpy.ops.wm.redraw_timer(type="DRAW_SWAP", iterations=3)  # --Work quite good but Slow down volume Render

        ############################# END LOOP ##################################

    # Join Planes Make Cube Voxel :
    bpy.ops.object.select_all(action="DESELECT")
    for obj in PlansList:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    bpy.ops.object.join()

    Voxel = bpy.context.object
    PatientName = DcmInfo["PatientName"]
    PatientID = DcmInfo["PatientID"]
    Preffix = PatientName or PatientID
    # if Preffix:
    #     Voxel.name = f"{Preffix}_CTVolume"
    # else:
    #     Voxel.name = "CTVolume"
    Voxel.name = "CTVolume"
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")

    Voxel.matrix_world = TransformMatrix

    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area3D = area
            for space in area3D.spaces:
                if space.type == "VIEW_3D":
                    space3D = space
                    break
            for region in area3D.regions:
                if region.type == "WINDOW":
                    r3D = region
                    break
    override = bpy.context.copy()
    override["area"] = area3D
    override["space_data"] = space3D
    override["region"] = r3D
    bpy.ops.view3d.view_selected(override, use_all_regions=False)

    for scr in bpy.data.screens:
        # if scr.name in ["Layout", "Scripting", "Shading"]:
        for area in [ar for ar in scr.areas if ar.type == "VIEW_3D"]:
            for space in [sp for sp in area.spaces if sp.type == "VIEW_3D"]:
                space.shading.type = "MATERIAL"

    for i in range(3):
        Voxel.lock_location[i] = True
        Voxel.lock_rotation[i] = True
        Voxel.lock_scale[i] = True

    Finish = time.perf_counter()
    print(f"CT-Scan loaded in {Finish-Start} secondes")


def Scene_Settings():
    # Set World Shader node :
    WorldNodes = bpy.data.worlds["World"].node_tree.nodes
    WColor = WorldNodes["Background"].inputs[0].default_value = (0.6, 0.6, 0.6, 0.6)
    WStrength = WorldNodes["Background"].inputs[1].default_value = 1.5

    # scene shading lights
    for scr in bpy.data.screens:
        for area in [ar for ar in scr.areas if ar.type == "VIEW_3D"]:
            for space in [sp for sp in area.spaces if sp.type == "VIEW_3D"]:
                # 3DView Shading Methode : in {'WIREFRAME', 'SOLID', 'MATERIAL', 'RENDERED'}
                space.shading.type = "MATERIAL"

                # 'Material' Shading Light method :
                space.shading.use_scene_lights = True
                space.shading.use_scene_world = False

                # 'RENDERED' Shading Light method :
                # space.shading.use_scene_lights_render = False
                # space.shading.use_scene_world_render = True

                space.shading.studio_light = "forest.exr"
                space.shading.studiolight_rotate_z = 0
                space.shading.studiolight_intensity = 1.5
                space.shading.studiolight_background_alpha = 0.0
                space.shading.studiolight_background_blur = 0.0

                space.shading.render_pass = "COMBINED"

                space.shading.type = "SOLID"
                space.shading.color_type = "TEXTURE"
                space.shading.light = "MATCAP"
                space.shading.studio_light = "basic_side.exr"

    scn = bpy.context.scene
    scn.render.engine = "BLENDER_EEVEE"
    scn.eevee.use_gtao = True
    scn.eevee.gtao_distance = 15
    scn.eevee.gtao_factor = 2.0
    scn.eevee.gtao_quality = 0.4
    scn.eevee.use_gtao_bounce = True
    scn.eevee.use_gtao_bent_normals = True
    scn.eevee.shadow_cube_size = "512"
    scn.eevee.shadow_cascade_size = "512"
    scn.eevee.use_soft_shadows = True
    scn.eevee.taa_samples = 16
    scn.display_settings.display_device = "None"
    scn.view_settings.look = "Medium Low Contrast"
    scn.view_settings.exposure = 0.0
    scn.view_settings.gamma = 1.0


def MoveToCollection(obj, CollName):

    OldColl = obj.users_collection  # list of all collection the obj is in
    NewColl = bpy.data.collections.get(CollName)
    if not NewColl:
        NewColl = bpy.data.collections.new(CollName)
        bpy.context.scene.collection.children.link(NewColl)
    if not obj in NewColl.objects[:]:
        NewColl.objects.link(obj)  # link obj to scene

    for Coll in OldColl:  # unlink from all  precedent obj collections
        if Coll is not NewColl:
            Coll.objects.unlink(obj)


#################################################################################################
# Add Slices :
#################################################################################################
def AxialSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = BDENTAL_Props.Nrrd255Path
    SlicesDir = BDENTAL_Props.SlicesDir
    DcmInfo = eval(BDENTAL_Props.DcmInfo)
    TransformMatrix = DcmInfo["TransformMatrix"]

    ImagePath = os.path.join(SlicesDir, "AXIAL_SLICE.png")
    Plane = bpy.context.scene.objects["AXIAL_SLICE"]

    if Plane and os.path.exists(ImageData):

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D_255 = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D_255.GetSpacing()
        Sz = Size = Image3D_255.GetSize()
        DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D_255.SetOrigin(Ortho_Origin)
        Image3D_255.SetDirection(np.identity(3).flatten())
        Origin = Image3D_255.GetOrigin()
        Direction = Image3D_255.GetDirection()
        P0 = Image3D_255.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
        P_diagonal = Image3D_255.TransformContinuousIndexToPhysicalPoint(
            (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
        )
        NewVCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5

        # Output Parameters :
        Out_Origin = [Origin[0], Origin[1], 0]
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
            Image3D_255,
            Out_Size,
            Euler3D,
            sitk.sitkLinear,
            Out_Origin,
            Out_Spacing,
            Out_Direction,
            0,
        )
        #############################################
        # Write Image :
        Array = sitk.GetArrayFromImage(Image2D)
        Flipped_Array = np.flipud(Array.reshape(Array.shape[1], Array.shape[2]))
        cv2.imwrite(ImagePath, Flipped_Array)
        #############################################
        # Update Blender Image data :
        BlenderImage = bpy.data.images.get("AXIAL_SLICE.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("AXIAL_SLICE.png")
        BlenderImage.reload()


def CoronalSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = BDENTAL_Props.Nrrd255Path
    SlicesDir = BDENTAL_Props.SlicesDir
    DcmInfo = eval(BDENTAL_Props.DcmInfo)
    TransformMatrix = DcmInfo["TransformMatrix"]

    ImagePath = os.path.join(SlicesDir, "CORONAL_SLICE.png")
    Plane = bpy.context.scene.objects["CORONAL_SLICE"]

    if Plane and os.path.exists(ImageData):

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D_255 = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D_255.GetSpacing()
        Sz = Size = Image3D_255.GetSize()
        DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D_255.SetOrigin(Ortho_Origin)
        Image3D_255.SetDirection(np.identity(3).flatten())
        Origin = Image3D_255.GetOrigin()
        Direction = Image3D_255.GetDirection()
        P0 = Image3D_255.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
        P_diagonal = Image3D_255.TransformContinuousIndexToPhysicalPoint(
            (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
        )
        NewVCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5

        # Output Parameters :
        Out_Origin = [Origin[0], Origin[1], 0]
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
            Image3D_255,
            Out_Size,
            Euler3D,
            sitk.sitkLinear,
            Out_Origin,
            Out_Spacing,
            Out_Direction,
            0,
        )
        #############################################
        # Write Image :
        Array = sitk.GetArrayFromImage(Image2D)
        Flipped_Array = np.flipud(Array.reshape(Array.shape[1], Array.shape[2]))
        cv2.imwrite(ImagePath, Flipped_Array)
        #############################################
        # Update Blender Image data :
        BlenderImage = bpy.data.images.get("CORONAL_SLICE.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("CORONAL_SLICE.png")
        BlenderImage.reload()


def SagitalSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = BDENTAL_Props.Nrrd255Path
    SlicesDir = BDENTAL_Props.SlicesDir
    DcmInfo = eval(BDENTAL_Props.DcmInfo)
    TransformMatrix = DcmInfo["TransformMatrix"]

    ImagePath = os.path.join(SlicesDir, "SAGITAL_SLICE.png")
    Plane = bpy.context.scene.objects["SAGITAL_SLICE"]

    if Plane and os.path.exists(ImageData):

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D_255 = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D_255.GetSpacing()
        Sz = Size = Image3D_255.GetSize()
        DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D_255.SetOrigin(Ortho_Origin)
        Image3D_255.SetDirection(np.identity(3).flatten())
        Origin = Image3D_255.GetOrigin()
        Direction = Image3D_255.GetDirection()
        P0 = Image3D_255.TransformContinuousIndexToPhysicalPoint((0, 0, 0))
        P_diagonal = Image3D_255.TransformContinuousIndexToPhysicalPoint(
            (Sz[0] - 1, Sz[1] - 1, Sz[2] - 1)
        )
        NewVCenter = (Vector(P0) + Vector(P_diagonal)) * 0.5

        # Output Parameters :
        Out_Origin = [Origin[0], Origin[1], 0]
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
            Image3D_255,
            Out_Size,
            Euler3D,
            sitk.sitkLinear,
            Out_Origin,
            Out_Spacing,
            Out_Direction,
            0,
        )
        #############################################
        # Write Image :
        Array = sitk.GetArrayFromImage(Image2D)
        Flipped_Array = np.flipud(Array.reshape(Array.shape[1], Array.shape[2]))
        cv2.imwrite(ImagePath, Flipped_Array)
        #############################################
        # Update Blender Image data :
        BlenderImage = bpy.data.images.get("SAGITAL_SLICE.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("SAGITAL_SLICE.png")
        BlenderImage.reload()


####################################################################
def AddAxialSlice():

    name = "AXIAL_SLICE"
    DcmInfo = eval(bpy.context.scene.BDENTAL_Props.DcmInfo)
    Sp, Sz, Origin, Direction, VC = (
        DcmInfo["Spacing"],
        DcmInfo["Size"],
        DcmInfo["Origin"],
        DcmInfo["Direction"],
        DcmInfo["VolumeCenter"],
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
    AxialDims = Vector((DimX, DimY, 0.0))
    AxialPlane.dimensions = AxialDims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    AxialPlane.location = VC
    # Add Material :
    mat = bpy.data.materials.get("AXIAL_SLICE_mat") or bpy.data.materials.new(
        "AXIAL_SLICE_mat"
    )

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
    ImageName = "AXIAL_SLICE.png"
    ImagePath = os.path.join(SlicesDir, ImageName)

    # write "AXIAL_SLICE.png" to here ImagePath
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


def AddCoronalSlice():

    name = "CORONAL_SLICE"
    DcmInfo = eval(bpy.context.scene.BDENTAL_Props.DcmInfo)
    Sp, Sz, Origin, Direction, VC = (
        DcmInfo["Spacing"],
        DcmInfo["Size"],
        DcmInfo["Origin"],
        DcmInfo["Direction"],
        DcmInfo["VolumeCenter"],
    )

    DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])

    # Remove old Slices and their data meshs :
    OldSlices = [obj for obj in bpy.context.view_layer.objects if name in obj.name]
    OldSliceMeshs = [mesh for mesh in bpy.data.meshes if name in mesh.name]

    for obj in OldSlices:
        bpy.data.objects.remove(obj)
    for mesh in OldSliceMeshs:
        bpy.data.meshes.remove(mesh)

    # Add CORONAL :
    bpy.ops.mesh.primitive_plane_add()
    CoronalPlane = bpy.context.active_object
    CoronalPlane.name = name
    CoronalPlane.data.name = f"{name}_mesh"
    CoronalPlane.rotation_mode = "XYZ"
    CoronalDims = Vector((DimX, DimY, 0.0))
    CoronalPlane.dimensions = CoronalDims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    CoronalPlane.rotation_euler = Euler((math.pi / 2, 0.0, 0.0), "XYZ")
    CoronalPlane.location = VC
    # Add Material :
    mat = bpy.data.materials.get("CORONAL_SLICE_mat") or bpy.data.materials.new(
        "CORONAL_SLICE_mat"
    )

    for slot in CoronalPlane.material_slots:
        bpy.ops.object.material_slot_remove()
    bpy.ops.object.material_slot_add()
    CoronalPlane.active_material = mat

    mat.use_nodes = True
    node_tree = mat.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    for node in nodes:
        if node.type != "OUTPUT_MATERIAL":
            nodes.remove(node)
    SlicesDir = bpy.context.scene.BDENTAL_Props.SlicesDir
    ImageName = "CORONAL_SLICE.png"
    ImagePath = os.path.join(SlicesDir, ImageName)

    # write "CORONAL_SLICE.png" to here ImagePath
    CoronalSliceUpdate(bpy.context.scene)

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
    [
        post_handlers.remove(h)
        for h in post_handlers
        if h.__name__ == "CoronalSliceUpdate"
    ]
    post_handlers.append(CoronalSliceUpdate)


def AddSagitalSlice():

    name = "SAGITAL_SLICE"
    DcmInfo = eval(bpy.context.scene.BDENTAL_Props.DcmInfo)
    Sp, Sz, Origin, Direction, VC = (
        DcmInfo["Spacing"],
        DcmInfo["Size"],
        DcmInfo["Origin"],
        DcmInfo["Direction"],
        DcmInfo["VolumeCenter"],
    )

    DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])

    # Remove old Slices and their data meshs :
    OldSlices = [obj for obj in bpy.context.view_layer.objects if name in obj.name]
    OldSliceMeshs = [mesh for mesh in bpy.data.meshes if name in mesh.name]

    for obj in OldSlices:
        bpy.data.objects.remove(obj)
    for mesh in OldSliceMeshs:
        bpy.data.meshes.remove(mesh)

    # Add SAGITAL :
    bpy.ops.mesh.primitive_plane_add()
    SagitalPlane = bpy.context.active_object
    SagitalPlane.name = name
    SagitalPlane.data.name = f"{name}_mesh"
    SagitalPlane.rotation_mode = "XYZ"
    SagitalDims = Vector((DimX, DimY, 0.0))
    SagitalPlane.dimensions = SagitalDims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    SagitalPlane.rotation_euler = Euler((math.pi / 2, 0.0, math.pi / 2), "XYZ")
    SagitalPlane.location = VC
    # Add Material :
    mat = bpy.data.materials.get("SAGITAL_SLICE_mat") or bpy.data.materials.new(
        "SAGITAL_SLICE_mat"
    )

    for slot in SagitalPlane.material_slots:
        bpy.ops.object.material_slot_remove()
    bpy.ops.object.material_slot_add()
    SagitalPlane.active_material = mat

    mat.use_nodes = True
    node_tree = mat.node_tree
    nodes = node_tree.nodes
    links = node_tree.links

    for node in nodes:
        if node.type != "OUTPUT_MATERIAL":
            nodes.remove(node)
    SlicesDir = bpy.context.scene.BDENTAL_Props.SlicesDir
    ImageName = "SAGITAL_SLICE.png"
    ImagePath = os.path.join(SlicesDir, ImageName)

    # write "SAGITAL_SLICE.png" to here ImagePath
    SagitalSliceUpdate(bpy.context.scene)

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
    [
        post_handlers.remove(h)
        for h in post_handlers
        if h.__name__ == "SagitalSliceUpdate"
    ]
    post_handlers.append(SagitalSliceUpdate)


#############################################################################
# SimpleITK vtk Image to Mesh Functions :
#############################################################################
def HuTo255(Hu, Wmin, Wmax):
    V255 = int(((Hu - Wmin) / (Wmax - Wmin)) * 255)
    return V255


def ResizeImage(sitkImage, Ratio):
    image = sitkImage
    Sz = image.GetSize()
    Sp = image.GetSpacing()
    new_size = [int(Sz[0] * Ratio), int(Sz[1] * Ratio), int(Sz[2] * Ratio)]
    new_spacing = [Sp[0] / Ratio, Sp[1] / Ratio, Sp[2] / Ratio]
    ResizedImage = sitk.Resample(
        image1=image,
        size=new_size,
        transform=sitk.Transform(),
        interpolator=sitk.sitkLinear,
        outputOrigin=image.GetOrigin(),
        outputSpacing=new_spacing,
        outputDirection=image.GetDirection(),
        defaultPixelValue=0,
        outputPixelType=image.GetPixelID(),
    )
    return ResizedImage


def sitkTovtk(sitkImage):
    """Convert sitk image to a VTK image"""
    sitkArray = sitk.GetArrayFromImage(sitkImage)  # .astype(np.uint8)
    vtkImage = vtk.vtkImageData()

    Sp = Spacing = sitkImage.GetSpacing()
    Sz = Size = sitkImage.GetSize()

    vtkImage.SetDimensions(Sz)
    vtkImage.SetSpacing(Sp)
    vtkImage.SetOrigin(0, 0, 0)
    vtkImage.SetDirectionMatrix(1, 0, 0, 0, 1, 0, 0, 0, 1)
    vtkImage.SetExtent(0, Sz[0] - 1, 0, Sz[1] - 1, 0, Sz[2] - 1)

    VtkArray = numpy_support.numpy_to_vtk(
        sitkArray.ravel(), deep=True, array_type=vtk.VTK_UNSIGNED_INT
    )
    VtkArray.SetNumberOfComponents(1)
    vtkImage.GetPointData().SetScalars(VtkArray)

    vtkImage.Modified()
    return vtkImage


def vtk_MC_Func(vtkImage, Treshold):
    MCFilter = vtk.vtkMarchingCubes()
    MCFilter.ComputeNormalsOn()
    MCFilter.SetValue(0, Treshold)
    MCFilter.SetInputData(vtkImage)
    MCFilter.Update()
    mesh = vtk.vtkPolyData()
    mesh.DeepCopy(MCFilter.GetOutput())
    return mesh


def vtkMeshReduction(mesh, reduction):
    decimatFilter = vtk.vtkQuadricDecimation()
    decimatFilter.SetInputData(mesh)
    decimatFilter.SetTargetReduction(reduction)
    decimatFilter.Update()
    mesh.DeepCopy(decimatFilter.GetOutput())
    return mesh


def vtkSmoothMesh(mesh, Iterations):
    SmoothFilter = vtk.vtkSmoothPolyDataFilter()
    SmoothFilter.SetInputData(mesh)
    SmoothFilter.SetNumberOfIterations(int(Iterations))
    SmoothFilter.SetFeatureAngle(45)
    SmoothFilter.SetRelaxationFactor(0.05)
    SmoothFilter.Update()
    mesh.DeepCopy(SmoothFilter.GetOutput())
    return mesh


def vtkTransformMesh(mesh, Matrix):
    """Transform a mesh using VTK's vtkTransformPolyData filter."""

    Transform = vtk.vtkTransform()
    Transform.SetMatrix(Matrix)

    transformFilter = vtk.vtkTransformPolyDataFilter()
    transformFilter.SetInputData(mesh)
    transformFilter.SetTransform(Transform)
    transformFilter.Update()
    mesh.DeepCopy(transformFilter.GetOutput())
    return mesh


def vtkfillholes(mesh, size):
    FillHolesFilter = vtk.vtkFillHolesFilter()
    FillHolesFilter.SetInputData(mesh)
    FillHolesFilter.SetHoleSize(size)
    FillHolesFilter.Update()
    mesh.DeepCopy(FillHolesFilter.GetOutput())
    return mesh


def vtkCleanMesh(mesh, connectivityFilter=False):
    """Clean a mesh using VTK's CleanPolyData filter."""

    ConnectFilter = vtk.vtkPolyDataConnectivityFilter()
    CleanFilter = vtk.vtkCleanPolyData()

    if connectivityFilter:

        ConnectFilter.SetInputData(mesh)
        ConnectFilter.SetExtractionModeToLargestRegion()
        CleanFilter.SetInputConnection(ConnectFilter.GetOutputPort())

    else:
        CleanFilter.SetInputData(mesh)

    CleanFilter.Update()
    mesh.DeepCopy(CleanFilter.GetOutput())
    return mesh


def sitkToContourArray(sitkImage, HuMin, HuMax, Wmin, Wmax, Thikness):
    """Convert sitk image to a VTK image"""

    def HuTo255(Hu, Wmin, Wmax):
        V255 = ((Hu - Wmin) / (Wmax - Wmin)) * 255
        return V255

    Image3D_255 = sitk.Cast(
        sitk.IntensityWindowing(
            sitkImage,
            windowMinimum=Wmin,
            windowMaximum=Wmax,
            outputMinimum=0.0,
            outputMaximum=255.0,
        ),
        sitk.sitkUInt8,
    )
    Array = sitk.GetArrayFromImage(Image3D_255)
    ContourArray255 = Array.copy()
    for i in range(ContourArray255.shape[0]):
        Slice = ContourArray255[i, :, :]
        ret, binary = cv2.threshold(
            Slice,
            HuTo255(HuMin, Wmin, Wmax),
            HuTo255(HuMax, Wmin, Wmax),
            cv2.THRESH_BINARY,
        )
        contours, hierarchy = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        SliceContour = np.ones(binary.shape, dtype="uint8")
        cv2.drawContours(SliceContour, contours, -1, 255, Thikness)

        ContourArray255[i, :, :] = SliceContour

    return ContourArray255


def vtkContourFilter(vtkImage, isovalue=0.0):
    """Extract an isosurface from a volume."""

    ContourFilter = vtk.vtkContourFilter()
    ContourFilter.SetInputData(vtkImage)
    ContourFilter.SetValue(0, isovalue)
    ContourFilter.Update()
    mesh = vtk.vtkPolyData()
    mesh.DeepCopy(ContourFilter.GetOutput())
    return mesh
