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
    WColor = WorldNodes["Background"].inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    WStrength = WorldNodes["Background"].inputs[1].default_value = 2.0

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
                space.shading.studiolight_intensity = 2.0
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
