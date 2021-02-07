# Python imports :
import os, sys, shutil
from os.path import join, dirname, exists,abspath

from math import degrees, radians, pi
import numpy as np
from time import sleep, perf_counter as Tcounter
from queue import Queue
from importlib import reload  


# Blender Imports :
import bpy
import bmesh
from mathutils import Matrix, Vector, Euler, kdtree

import SimpleITK as sitk
import vtk
import cv2
try :
    cv2 = reload(cv2)
except ImportError :
    pass
from vtk.util import numpy_support
from vtk import vtkCommand

# Global Variables :

ProgEvent = vtkCommand.ProgressEvent

#######################################################################################
# Popup message box function :
#######################################################################################

def ShowMessageBox(message=[], title="INFO", icon="INFO"):
    def draw(self, context):
        for txtLine in message:
            self.layout.label(text=txtLine)

    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)

#######################################################################################
# Load CT Scan functions :
#######################################################################################
def AbsPath(P):
    if P.startswith('//') :
        P = abspath(bpy.path.abspath(P))
    return P   

def RelPath(P):
    if not P.startswith('//') :
        P = bpy.path.relpath(abspath(P))
    return P
############################
# Make directory function :
############################
def make_directory(Root, DirName):

    DirPath = join(Root, DirName)
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

def PlaneCut(Target, Plane, inner=False, outer=False, fill=False):

    bpy.ops.object.select_all(action="DESELECT")
    Target.select_set(True)
    bpy.context.view_layer.objects.active = Target

    Pco = Plane.matrix_world.translation
    Pno = Plane.matrix_world.to_3x3().transposed()[2]

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.bisect(
        plane_co=Pco,
        plane_no=Pno,
        use_fill=fill,
        clear_inner=inner,
        clear_outer=outer,
    )
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")

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
    mesh_data = bpy.data.meshes.new(f"{Name}_mesh")
    mesh_data.from_pydata(verts, [], faces)
    uvs = mesh_data.uv_layers.new(name=f"{Name}_uv")
    # Returns True if any invalid geometry was removed.
    corrections = mesh_data.validate(verbose=True, clean_customdata=True)
    # Load BMesh with mesh data.
    bm = bmesh.new()
    bm.from_mesh(mesh_data)
    bm.to_mesh(mesh_data)
    bm.free()
    mesh_data.update(calc_edges=True, calc_edges_loose=True)

    return mesh_data

def AddPlaneObject(Name, mesh, CollName):
    Plane_obj = bpy.data.objects.new(Name, mesh)
    Coll = bpy.data.collections.get(CollName)
    if not Coll:
        Coll = bpy.data.collections.new(CollName)
        bpy.context.scene.collection.children.link(Coll)
    if not Plane_obj in Coll.objects[:]:
        Coll.objects.link(Plane_obj)

    return Plane_obj

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

def VolumeRender(DcmInfo, GpShader, ShadersBlendFile):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    Sp = Spacing = DcmInfo["RenderSp"]
    Sz = Size = DcmInfo["RenderSz"]
    Origin = DcmInfo["Origin"]
    Direction = DcmInfo["Direction"]
    TransformMatrix = DcmInfo["TransformMatrix"]
    Preffix = DcmInfo["PatientID"]
    DimX, DimY, DimZ = (Sz[0] * Sp[0], Sz[1] * Sp[1], Sz[2] * Sp[2])
    Offset = Sp[2]
    # ImagesList = sorted(os.listdir(PngDir))
    ImagesNamesList = sorted([img.name for img in bpy.data.images if img.name.startswith(Preffix)])
    ImagesList = [bpy.data.images[Name] for Name in ImagesNamesList]
    #################################################################################
    Start = Tcounter()
    #################################################################################
    # ///////////////////////////////////////////////////////////////////////////#
    ######################## Set Render settings : #############################
    Scene_Settings()
    ###################### Change to ORTHO persp with nice view angle :##########
    # ViewMatrix = Matrix(
    #     (
    #         (0.8435, -0.5371, -0.0000, 1.2269),
    #         (0.2497, 0.3923, 0.8853, -15.1467),
    #         (-0.4755, -0.7468, 0.4650, -55.2801),
    #         (0.0000, 0.0000, 0.0000, 1.0000),
    #     )
    # )
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
                r3d.view_distance = 400
                r3d.view_matrix = ViewMatrix
                r3d.update()

    ################### Load all PNG images : ###############################
    # for ImagePNG in ImagesList:
    #     image_path = join(PngDir, ImagePNG)
    #     bpy.data.images.load(image_path)

    # bpy.ops.file.pack_all()

    ###############################################################################################
    # Add Planes with textured material :
    ###############################################################################################
    PlansList = []
    ############################# START LOOP ##################################

    for i, ImageData in enumerate(ImagesList):
        # # Add Plane :
        # ##########################################
        Preffix = "PLANE_"
        Name = f"{Preffix}{i}"
        mesh = AddPlaneMesh(DimX, DimY, Name)
        CollName = "CT Voxel"

        obj = AddPlaneObject(Name, mesh, CollName)
        obj.location[2] = i * Offset
        PlansList.append(obj)
        ##########################################
        # # Add Plane :
        # Preffix = "PLANE_"
        # Name = f"{Preffix}{i}"
        # CollName = "CT Voxel"
        # bpy.ops.mesh.primitive_plane_add()
        # obj = bpy.context.active_object
        # obj.dimensions = (DimX, DimY, 0)
        # obj.name = Name
        # obj.data.name = Name
        # obj.location[2] = i * Offset
        # MoveToCollection(obj, CollName)
        # PlansList.append(obj)
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

        # ImageData = bpy.data.images.get(ImagePNG)
        TextureCoord = AddNode(
            nodes, type="ShaderNodeTexCoord", name="TextureCoord"
        )
        ImageTexture = AddNode(
            nodes, type="ShaderNodeTexImage", name="Image Texture"
        )
        ImageTexture.image = ImageData
        ImageData.colorspace_settings.name = "Non-Color"

        materialOutput = nodes["Material Output"]

        links.new(TextureCoord.outputs[0], ImageTexture.inputs[0])

        # Load VGS Group Node :
        VGS = bpy.data.node_groups.get(GpShader)
        if not VGS:
            filepath = join(ShadersBlendFile, "NodeTree", GpShader)
            directory = join(ShadersBlendFile, "NodeTree")
            filename = GpShader
            bpy.ops.wm.append(
                filepath=filepath, filename=filename, directory=directory
            )
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

        # print(f"{ImagePNG} Processed ...")
        # bpy.ops.wm.redraw_timer(type="DRAW_SWAP", iterations=3)  # --Work good but Slow down volume Render

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

    Finish = Tcounter()
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
                space.shading.use_scene_lights_render = False
                space.shading.use_scene_world_render = True

                space.shading.studio_light = "forest.exr"
                space.shading.studiolight_rotate_z = 0
                space.shading.studiolight_intensity = 1.5
                space.shading.studiolight_background_alpha = 0.0
                space.shading.studiolight_background_blur = 0.0

                space.shading.render_pass = "COMBINED"

                space.shading.type = "SOLID"
                space.shading.color_type = "TEXTURE"
                # space.shading.light = "MATCAP"
                # space.shading.studio_light = "basic_side.exr"
                bpy.context.space_data.shading.light = "STUDIO"
                bpy.context.space_data.shading.studio_light = "outdoor.sl"
                bpy.context.space_data.shading.show_cavity = True
                bpy.context.space_data.shading.curvature_ridge_factor = 0.5
                bpy.context.space_data.shading.curvature_valley_factor = 0.5

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
    scn.eevee.use_ssr = True

#################################################################################################
# Add Slices :
#################################################################################################
def AxialSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = AbsPath(BDENTAL_Props.Nrrd255Path)
    Plane = bpy.context.scene.objects.get("1_AXIAL_SLICE")

    Condition1 = exists(ImageData)
    Condition2 = (bpy.context.view_layer.objects.active == Plane)

    if Plane and Condition1 and Condition2 :

        SlicesDir = AbsPath(BDENTAL_Props.SlicesDir)
        DcmInfo = eval(BDENTAL_Props.DcmInfo)
        TransformMatrix = DcmInfo["TransformMatrix"]
        ImagePath = join(SlicesDir, "1_AXIAL_SLICE.png")

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D_255 = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D_255.GetSpacing()
        Sz = Size = Image3D_255.GetSize()
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D_255.SetOrigin(Ortho_Origin)
        Image3D_255.SetDirection(np.identity(3).flatten())
        
        # Output Parameters :
        Out_Origin = [Ortho_Origin[0], Ortho_Origin[1], 0]
        Out_Direction = Vector(np.identity(3).flatten())
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
        Euler3D.SetCenter((0, 0, 0))
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
        BlenderImage = bpy.data.images.get("1_AXIAL_SLICE.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("1_AXIAL_SLICE.png")
        BlenderImage.reload()

def CoronalSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = AbsPath(BDENTAL_Props.Nrrd255Path)
    Plane = bpy.context.scene.objects.get("2_CORONAL_SLICE")

    Condition1 = exists(ImageData)
    Condition2 = (bpy.context.view_layer.objects.active == Plane)

    if Plane and Condition1 and Condition2 :

        SlicesDir = AbsPath(BDENTAL_Props.SlicesDir)
        DcmInfo = eval(BDENTAL_Props.DcmInfo)
        TransformMatrix = DcmInfo["TransformMatrix"]
        ImagePath = join(SlicesDir, "2_CORONAL_SLICE.png")

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D_255 = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D_255.GetSpacing()
        Sz = Size = Image3D_255.GetSize()
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D_255.SetOrigin(Ortho_Origin)
        Image3D_255.SetDirection(np.identity(3).flatten())
        
        # Output Parameters :
        Out_Origin = [Ortho_Origin[0], Ortho_Origin[1], 0]
        Out_Direction = Vector(np.identity(3).flatten())
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
        Euler3D.SetCenter((0, 0, 0))
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
        BlenderImage = bpy.data.images.get("2_CORONAL_SLICE.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("2_CORONAL_SLICE.png")
        BlenderImage.reload()

def SagitalSliceUpdate(scene):

    BDENTAL_Props = bpy.context.scene.BDENTAL_Props
    ImageData = AbsPath(BDENTAL_Props.Nrrd255Path)
    Plane = bpy.context.scene.objects.get("3_SAGITAL_SLICE")

    Condition1 = exists(ImageData)
    Condition2 = (bpy.context.view_layer.objects.active == Plane)

    if Plane and Condition1 and Condition2 :

        SlicesDir = AbsPath(BDENTAL_Props.SlicesDir)
        DcmInfo = eval(BDENTAL_Props.DcmInfo)
        TransformMatrix = DcmInfo["TransformMatrix"]
        ImagePath = join(SlicesDir, "3_SAGITAL_SLICE.png")

        #########################################
        #########################################
        # Get ImageData Infos :
        Image3D_255 = sitk.ReadImage(ImageData)
        Sp = Spacing = Image3D_255.GetSpacing()
        Sz = Size = Image3D_255.GetSize()
        Ortho_Origin = -0.5 * np.array(Sp) * (np.array(Sz) - np.array((1, 1, 1)))
        Image3D_255.SetOrigin(Ortho_Origin)
        Image3D_255.SetDirection(np.identity(3).flatten())
        
        # Output Parameters :
        Out_Origin = [Ortho_Origin[0], Ortho_Origin[1], 0]
        Out_Direction = Vector(np.identity(3).flatten())
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
        Euler3D.SetCenter((0, 0, 0))
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
        BlenderImage = bpy.data.images.get("3_SAGITAL_SLICE.png")
        if not BlenderImage:
            bpy.data.images.load(ImagePath)
            BlenderImage = bpy.data.images.get("3_SAGITAL_SLICE.png")
        BlenderImage.reload()

####################################################################
def AddAxialSlice():

    name = "1_AXIAL_SLICE"
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
    mat = bpy.data.materials.get("1_AXIAL_SLICE_mat") or bpy.data.materials.new(
        "1_AXIAL_SLICE_mat"
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
    SlicesDir = AbsPath(bpy.context.scene.BDENTAL_Props.SlicesDir)
    ImageName = "1_AXIAL_SLICE.png"
    ImagePath = join(SlicesDir, ImageName)

    # write "1_AXIAL_SLICE.png" to here ImagePath
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
    [
        post_handlers.remove(h)
        for h in post_handlers
        if h.__name__ == "AxialSliceUpdate"
    ]
    post_handlers.append(AxialSliceUpdate)
    

def AddCoronalSlice():

    name = "2_CORONAL_SLICE"
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
    CoronalPlane.rotation_euler = Euler((pi / 2, 0.0, 0.0), "XYZ")
    CoronalPlane.location = VC
    # Add Material :
    mat = bpy.data.materials.get("2_CORONAL_SLICE_mat") or bpy.data.materials.new(
        "2_CORONAL_SLICE_mat"
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
    SlicesDir = AbsPath(bpy.context.scene.BDENTAL_Props.SlicesDir)
    ImageName = "2_CORONAL_SLICE.png"
    ImagePath = join(SlicesDir, ImageName)

    # write "2_CORONAL_SLICE.png" to here ImagePath
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

    name = "3_SAGITAL_SLICE"
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
    SagitalPlane.rotation_euler = Euler((pi / 2, 0.0, pi / 2), "XYZ")
    SagitalPlane.location = VC
    # Add Material :
    mat = bpy.data.materials.get("3_SAGITAL_SLICE_mat") or bpy.data.materials.new(
        "3_SAGITAL_SLICE_mat"
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
    SlicesDir = AbsPath(bpy.context.scene.BDENTAL_Props.SlicesDir)
    ImageName = "3_SAGITAL_SLICE.png"
    ImagePath = join(SlicesDir, ImageName)

    # write "3_SAGITAL_SLICE.png" to here ImagePath
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
        image,
        new_size,
        sitk.Transform(),
        sitk.sitkLinear,
        image.GetOrigin(),
        new_spacing,
        image.GetDirection(),
        0,
    )
    return ResizedImage

# def VTK_Terminal_progress(caller, event, q):
#     ProgRatio = round(float(caller.GetProgress()), 2)
#     q.put(
#         ["loop", f"PROGRESS : {step} processing...", "", {start}, {finish}, ProgRatio]
#     )

def VTKprogress(caller, event):
    pourcentage = int(caller.GetProgress() * 100)
    calldata = str(int(caller.GetProgress() * 100)) + " %"
    # print(calldata)
    sys.stdout.write(f"\r {calldata}")
    sys.stdout.flush()
    progress_bar(pourcentage, Delay=1)

def TerminalProgressBar(
    q,
    counter_start,
    iter=100,
    maxfill=20,
    symb1="\u2588",
    symb2="\u2502",
    periode=10,
):

    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="cp65001")
        # cmd = "chcp 65001 & set PYTHONIOENCODING=utf-8"
        # subprocess.call(cmd, shell=True)

    print("\n")

    while True:
        if not q.empty():
            signal = q.get()

            if "End" in signal[0]:
                finish = Tcounter()
                line = f"{symb1*maxfill}  100% Finished.------Total Time : {round(finish-counter_start,2)}"
                # clear sys.stdout line and return to line start:
                # sys.stdout.write("\r")
                # sys.stdout.write(" " * 100)
                # sys.stdout.flush()
                # sys.stdout.write("\r")
                # write line :
                sys.stdout.write("\r" + " " * 80 + "\r" + line)  # f"{Char}"*i*2
                sys.stdout.flush()
                break

            if "GuessTime" in signal[0]:
                _, Uptxt, Lowtxt, start, finish, periode = signal
                for i in range(iter):

                    if q.empty():

                        ratio = start + (((i + 1) / iter) * (finish - start))
                        pourcentage = int(ratio * 100)
                        symb1_fill = int(ratio * maxfill)
                        symb2_fill = int(maxfill - symb1_fill)
                        line = f"{symb1*symb1_fill}{symb2*symb2_fill}  {pourcentage}% {Uptxt}"
                        # clear sys.stdout line and return to line start:
                        # sys.stdout.write("\r"+" " * 80)
                        # sys.stdout.flush()
                        # write line :
                        sys.stdout.write(
                            "\r" + " " * 80 + "\r" + line
                        )  # f"{Char}"*i*2
                        sys.stdout.flush()
                        sleep(periode / iter)
                    else:
                        break

            if "loop" in signal[0]:
                _, Uptxt, Lowtxt, start, finish, progFloat = signal
                ratio = start + (progFloat * (finish - start))
                pourcentage = int(ratio * 100)
                symb1_fill = int(ratio * maxfill)
                symb2_fill = int(maxfill - symb1_fill)
                line = (
                    f"{symb1*symb1_fill}{symb2*symb2_fill}  {pourcentage}% {Uptxt}"
                )
                # clear sys.stdout line and return to line start:
                # sys.stdout.write("\r")
                # sys.stdout.write(" " * 100)
                # sys.stdout.flush()
                # sys.stdout.write("\r")
                # write line :
                sys.stdout.write("\r" + " " * 80 + "\r" + line)  # f"{Char}"*i*2
                sys.stdout.flush()

        else:
            sleep(0.1)

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

def vtkMeshReduction(q, mesh, reduction, step, start, finish):
    """Reduce a mesh using VTK's vtkQuadricDecimation filter."""

    def VTK_Terminal_progress(caller, event):
        ProgRatio = round(float(caller.GetProgress()), 2)
        q.put(
            [
                "loop",
                f"PROGRESS : {step}...",
                "",
                start,
                finish,
                ProgRatio,
            ]
        )

    decimatFilter = vtk.vtkQuadricDecimation()
    decimatFilter.SetInputData(mesh)
    decimatFilter.SetTargetReduction(reduction)

    decimatFilter.AddObserver(ProgEvent, VTK_Terminal_progress)
    decimatFilter.Update()

    mesh.DeepCopy(decimatFilter.GetOutput())
    return mesh

def vtkSmoothMesh(q, mesh, Iterations, step, start, finish):
    """Smooth a mesh using VTK's vtkSmoothPolyData filter."""

    def VTK_Terminal_progress(caller, event):
        ProgRatio = round(float(caller.GetProgress()), 2)
        q.put(
            [
                "loop",
                f"PROGRESS : {step}...",
                "",
                start,
                finish,
                ProgRatio,
            ]
        )

    SmoothFilter = vtk.vtkSmoothPolyDataFilter()
    SmoothFilter.SetInputData(mesh)
    SmoothFilter.SetNumberOfIterations(int(Iterations))
    SmoothFilter.SetFeatureAngle(45)
    SmoothFilter.SetRelaxationFactor(0.05)
    SmoothFilter.AddObserver(ProgEvent, VTK_Terminal_progress)
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

def CV2_progress_bar(q, iter=100):
    while True:
        if not q.empty():
            signal = q.get()

            if "End" in signal[0]:
                pourcentage = 100
                Uptxt = "Finished."
                progress_bar(pourcentage, Uptxt)
                break
            if "GuessTime" in signal[0]:
                _, Uptxt, Lowtxt, start, finish, periode = signal
                for i in range(iter):

                    if q.empty():

                        ratio = start + (((i + 1) / iter) * (finish - start))
                        pourcentage = int(ratio * 100)
                        progress_bar(pourcentage, Uptxt)
                        sleep(periode / iter)
                    else:
                        break

            if "loop" in signal[0]:
                _, Uptxt, Lowtxt, start, finish, progFloat = signal
                ratio = start + (progFloat * (finish - start))
                pourcentage = int(ratio * 100)
                progress_bar(pourcentage, Uptxt)

        else:
            sleep(0.1)

def progress_bar(pourcentage, Uptxt, Lowtxt="", Title="BDENTAL", Delay=1):

    X, Y = WindowWidth, WindowHeight = (500, 100)
    BackGround = np.ones((Y, X, 3), dtype=np.uint8) * 255
    # Progress bar Parameters :
    maxFill = X - 70
    minFill = 40
    barColor = (50, 200, 0)
    BarHeight = 20
    barUp = Y - 60
    barBottom = barUp + BarHeight
    # Text :
    font = cv2.FONT_HERSHEY_SIMPLEX
    fontScale = 0.5
    fontThikness = 1
    fontColor = (0, 0, 0)
    lineStyle = cv2.LINE_AA

    chunk = (maxFill - 40) / 100

    img = BackGround.copy()
    fill = minFill + int(pourcentage * chunk)
    img[barUp:barBottom, minFill:fill] = barColor

    img = cv2.putText(
        img,
        f"{pourcentage}%",
        (maxFill + 10, barBottom - 8),
        # (fill + 10, barBottom - 10),
        font,
        fontScale,
        fontColor,
        fontThikness,
        lineStyle,
    )

    img = cv2.putText(
        img,
        Uptxt,
        (minFill, barUp - 10),
        font,
        fontScale,
        fontColor,
        fontThikness,
        lineStyle,
    )
    cv2.imshow(Title, img)

    cv2.waitKey(Delay)

    if pourcentage == 100:
        img = BackGround.copy()
        img[barUp:barBottom, minFill:maxFill] = (50, 200, 0)
        img = cv2.putText(
            img,
            "100%",
            (maxFill + 10, barBottom - 8),
            font,
            fontScale,
            fontColor,
            fontThikness,
            lineStyle,
        )

        img = cv2.putText(
            img,
            Uptxt,
            (minFill, barUp - 10),
            font,
            fontScale,
            fontColor,
            fontThikness,
            lineStyle,
        )
        cv2.imshow(Title, img)
        cv2.waitKey(Delay)
        sleep(4)
        cv2.destroyAllWindows()
