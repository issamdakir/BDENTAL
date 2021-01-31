# ----------------------------------------------------------
# File __init__.py
# ----------------------------------------------------------

#    Addon info
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
##############################################################################################
bl_info = {
    "name": "BDENTAL",  ###################Addon name
    "author": "Essaid Issam Dakir DMD",
    "version": (1, 0, 0),
    "blender": (2, 90, 1),  ################# Blender working version
    "location": "3D View -> UI SIDE PANEL ",
    "description": "3D Tools suite for Digital Dentistry",  ########### Addon description
    "warning": "",
    "doc_url": "",
    "tracker_url": "",
    "category": "Dental",  ################## Addon category
}
#############################################################################################
# IMPORTS :
#############################################################################################
# Python imports :
import sys, os, bpy
from importlib import import_module
from os.path import dirname, join, realpath, abspath, exists


sys.stdout.reconfigure(encoding="cp65001")  # activate unicode characters in windows CLI

#############################################################
def ImportReq(REQ_DICT):
    Pkgs = []
    for mod, pkg in REQ_DICT.items():
        try:
            import_module(mod)
        except ImportError:
            Pkgs.append(pkg)

    return Pkgs

###################################################
REQ_DICT = {
    "SimpleITK": "SimpleITK==2.0.2",
    "vtk": "vtk==9.0.1",
    "cv2.aruco": "opencv-contrib-python==4.4.0.46",  
}
ADDON_DIR = dirname(abspath(__file__))
REQ_DIR = join(ADDON_DIR, "Resources", "Requirements")

if not sys.path[0] == REQ_DIR :
    sys.path.insert(0, REQ_DIR)

NotFoundPkgs = ImportReq(REQ_DICT)

if NotFoundPkgs :
    ############################
    # Install Req Registration :
    ############################
    from .Operators import BDENTAL_InstallReq
    
    def register():

        BDENTAL_InstallReq.register()
     
    def unregister():

        BDENTAL_InstallReq.unregister()


    if __name__ == "__main__":
        register()      

else : 
    ######################
    # Addon Registration :
    ######################

    # Addon modules imports :
    from . import BDENTAL_Props, BDENTAL_Panel
    from .Operators import BDENTAL_ScanOperators

    
    addon_modules = [
        BDENTAL_Props,
        BDENTAL_Panel,
        BDENTAL_ScanOperators,
    ]
    init_classes = []


    def register():

        for module in addon_modules:
            module.register()
        for cl in init_classes:
            bpy.utils.register_class(cl)


    def unregister():
        for cl in init_classes:
            bpy.utils.unregister_class(cl)
        for module in reversed(addon_modules):
            module.unregister()


    if __name__ == "__main__":
        register()      

























# ADDON_DIR = dirname(abspath(__file__))
# REQ_DIR = join(ADDON_DIR, join(f"Resources{SS}Requirements"))
# REQ_ZIP = join(REQ_DIR, "BDENTAL_Req.zip")
# sys.path.insert(0, REQ_DIR)
# # if exists(REQ_ZIP):
# #     from BDENTAL_rarfile import RarFile

# #     with RarFile(REQ_RAR) as RarF:
# #         RarF.extract(RarF.namelist()[0])
# #     print("Requirements Un-Compressed!")

# if exists(REQ_ZIP):
#     with zipfile.ZipFile(REQ_ZIP, "r") as Zip_File:
#         Zip_File.extractall(REQ_DIR)
#     os.remove(REQ_ZIP)
#     print("Requirements Un-Compressed!")
# #############################################################


# # Addon modules imports :
# from . import BDENTAL_Props, BDENTAL_Panel
# from .Operators import BDENTAL_ScanOperators

# ############################################################################################
# # Registration :
# ############################################################################################
# addon_modules = [
#     BDENTAL_Props,
#     BDENTAL_Panel,
#     BDENTAL_ScanOperators,
# ]
# init_classes = []


# def register():

#     for module in addon_modules:
#         module.register()
#     for cl in init_classes:
#         bpy.utils.register_class(cl)


# def unregister():
#     for cl in init_classes:
#         bpy.utils.unregister_class(cl)
#     for module in reversed(addon_modules):
#         module.unregister()


# if __name__ == "__main__":
#     register()


# Requirements = {
#     "SimpleITK": "SimpleITK==2.0.2",
#     "vtk": "vtk==9.0.1",
#     "cv2.aruco": "opencv-contrib-python==4.4.0.46",  # working version4.4.0.46 # Uptodate 01082021: 4.5.1.48
# }


# def isConnected():
#     try:
#         sock = socket.create_connection(("www.google.com", 80))
#         if sock is not None:
#             print("Clossing socket")
#             sock.close
#         return True
#     except OSError:
#         pass
#         return False


# def BlenderRequirementsPipInstall(path, modules):
#     # Download and install requirement if not AddonPacked version:
#     if sys.platform == "win32":
#         Blender_python_path = sys.executable
#     if sys.platform == "darwin":
#         Blender_python_path = join(sys.base_exec_prefix, f"bin{SS}python3.7m")
#     subprocess.call(
#         f"{Blender_python_path} -m ensurepip ",
#         shell=True,
#     )
#     subprocess.call(
#         f"{Blender_python_path} -m pip install -U pip ",
#         shell=True,
#     )
#     print("Blender pip upgraded")

#     for module in modules:
#         command = f'{Blender_python_path} -m pip install {module} --target "{path}"'
#         subprocess.call(command, shell=True)
#         print(f"{module}Downloaded and installed")

#     ##########################
#     print("requirements installed successfuly.")


# ##########################################################################
# ##########################################################################
# NotFoundPkgs = []
# for mod, pkg in Requirements.items():
#     try:
#         import_module(mod)
#     except ImportError:
#         NotFoundPkgs.append(pkg)

# if NotFoundPkgs == []:

#     print("Requirement already installed")
#     # Addon modules imports :
#     from . import BDENTAL_Props, BDENTAL_Panel
#     from .Operators import BDENTAL_ScanOperators

#     ############################################################################################
#     # Registration :
#     ############################################################################################
#     addon_modules = [
#         BDENTAL_Props,
#         BDENTAL_Panel,
#         BDENTAL_ScanOperators,
#     ]
#     init_classes = []

#     def register():

#         for module in addon_modules:
#             module.register()
#         for cl in init_classes:
#             bpy.utils.register_class(cl)

#     def unregister():
#         for cl in init_classes:
#             bpy.utils.unregister_class(cl)
#         for module in reversed(addon_modules):
#             module.unregister()

#     if __name__ == "__main__":
#         register()

# else:

#     for pkg in NotFoundPkgs:
#         print(f"{pkg} : not installed")
#     ######################################################################################
#     if isConnected():
#         BlenderRequirementsPipInstall(path=REQ_DIR, modules=NotFoundPkgs)
#         # Addon modules imports :
#         from . import BDENTAL_Props, BDENTAL_Panel
#         from .Operators import BDENTAL_ScanOperators

#         addon_modules = [
#             BDENTAL_Props,
#             BDENTAL_Panel,
#             BDENTAL_ScanOperators,
#         ]
#         init_classes = []

#         ############################################################################################
#         # Registration :
#         ############################################################################################
#         def register():
#             for module in addon_modules:
#                 module.register()
#             for cl in init_classes:
#                 bpy.utils.register_class(cl)

#         def unregister():
#             for cl in init_classes:
#                 bpy.utils.unregister_class(cl)
#             for module in reversed(addon_modules):
#                 module.unregister()

#         if __name__ == "__main__":
#             register()

#     else:

#         def register():

#             message = "Please Check Internet Connexion and restart Blender! "
#             print(message)

#         def unregister():
#             pass

#         if __name__ == "__main__":
#             register()
