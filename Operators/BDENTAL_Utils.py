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


######################################################################################
# Volume load :
######################################################################################
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
                space.shading.studiolight_rotate_z = 120
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
    scn.eevee.taa_samples = 32
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


# def HuTo255(Hu, Wmin, Wmax):
#     V255 = ((Hu - Wmin) / (Wmax - Wmin)) * 255
#     return V255


# Wmin, Wmax = -400, 3000
# # print(HuTo255(-400, Wmin, Wmax))
# def ContourImage(ImgArray, HuMin, HuMax, Wmin, Wmax):
#     "extracts a coutour mask from image"
#     ret, binary = cv2.threshold(
#         ImgArray,
#         HuTo255(HuMin, Wmin, Wmax),
#         HuTo255(HuMax, Wmin, Wmax),
#         cv2.THRESH_BINARY,
#     )
#     contours, hierarchy = cv2.findContours(
#         binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
#     )
#     ContourArray = np.ones(binary.shape, dtype="uint8")
#     cv2.drawContours(ContourArray, contours, -1, 255, 1)
#     return ContourArray


# #########################################################################
# NrrdHuPath = R"C:\Users\ISSAM\Desktop\Nouveau dossier\ZAKHNOUF^KHADIJA_Image3DHu.nrrd"


# cv2.imwrite(img_Out, img_Slice)
# def Nrrdvtk(Nrrd):
#     """Convert a Nrrd image to a VTK image, via numpy."""

#     Image3D = sitk.ReadImage(Nrrd)
#     sitkArray = sitk.GetArrayFromImage(Image3D)
#     vtkImage = vtk.vtkImageData()

#     Sp = Spacing = Image3D.GetSpacing()
#     Sz = Size = Image3D.GetSize()
#     Origin = Image3D.GetOrigin()
#     Direction = Image3D.GetDirection()

#     vtkImage.SetDimensions(Sz)
#     vtkImage.SetSpacing(Sp)
#     vtkImage.SetOrigin(Origin)
#     vtkImage.SetExtent(0, Sz[0] - 1, 0, Sz[1] - 1, 0, Sz[2] - 1)

#     VtkArray = numpy_support.numpy_to_vtk(sitkArray.ravel())
#     VtkArray.SetNumberOfComponents(1)
#     vtkImage.GetPointData().SetScalars(VtkArray)

#     vtkImage.Modified()

#     return vtkImage


# Nrrd = R"C:\Users\ISSAM\Desktop\Test_Project\ZAKHNOUF^KHADIJA_Image3D.nrrd"
# vtkImage = Nrrdvtk(Nrrd)