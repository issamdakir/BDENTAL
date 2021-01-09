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
    "name": "BDENTAL SCAN VIEWER",  ###################Addon name
    "author": "Essaid Issam Dakir DMD",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),  ################# Blender working version
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
import sys, os, bpy, subprocess, socket, time, addon_utils, platform
from importlib import import_module

# activate unicode characters in windows CLI :
if platform.system() == "Windows":
    sys.stdout.reconfigure(encoding="cp65001")
    # cmd = "chcp 65001"  # "& set PYTHONIOENCODING=utf-8"
    # subprocess.call(cmd, shell=True)

#############################################################
# Add sys Paths : Addon directory and requirements directory
addon_dir = os.path.dirname(os.path.abspath(__file__))
requirements_path = os.path.join(addon_dir, "Resources\\Requirements")

sysPaths = [addon_dir, requirements_path]

for path in sysPaths:
    if not path in sys.path:
        sys.path.append(path)

Requirements = {
    "SimpleITK": "SimpleITK==2.0.2",
    "vtk": "vtk==9.0.1",
    "cv2": "opencv-contrib-python",  # working version4.4.0.46 # Uptodate 01082021: 4.5.1.48
}


def isConnected():
    try:
        sock = socket.create_connection(("www.google.com", 80))
        if sock is not None:
            print("Clossing socket")
            sock.close
        return True
    except OSError:
        pass
        return False


def BlenderRequirementsPipInstall(path, modules):
    # Download and install requirement if not AddonPacked version:
    Blender_python_path = os.path.join(sys.base_exec_prefix, "bin")
    site_packages = os.path.join(Blender_python_path, "lib\\site-packages\\*.*")
    subprocess.call(
        f"cd {Blender_python_path} && python -m ensurepip ",
        shell=True,
    )
    subprocess.call(
        f"cd {Blender_python_path} && python -m pip install -U pip ",
        shell=True,
    )
    print("Blender pip upgraded")

    for module in modules:
        command = f'cd "{Blender_python_path}" && python -m pip install {module} --target "{path}"'
        subprocess.call(command, shell=True)
        print(f"{module}Downloaded and installed")

    ##########################
    print("requirements installed successfuly.")


##########################################################################
##########################################################################
##########################################################################

# if (
#     "cv2" in os.listdir(requirements_path)
#     and "SimpleITK" in os.listdir(requirements_path)
#     and "vtk.py" in os.listdir(requirements_path)
# ):
NotFoundPkgs = []
for mod, pkg in Requirements.items():
    try:
        import_module(mod)
    except ImportError:
        NotFoundPkgs.append(pkg)

if NotFoundPkgs == []:

    print("Requirement already installed")
    # Addon modules imports :
    from . import BDENTAL_Props, BDENTAL_Panel
    from .Operators import BDENTAL_ScanOperators, AlignOperators

    ############################################################################################
    # Registration :
    ############################################################################################
    addon_modules = [
        BDENTAL_Props,
        BDENTAL_Panel,
        BDENTAL_ScanOperators,
        AlignOperators,
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

else:
    for pkg in NotFoundPkgs:
        print(f"{pkg} : not installed")
    ######################################################################################
    if isConnected():
        BlenderRequirementsPipInstall(path=requirements_path, modules=NotFoundPkgs)
        # Addon modules imports :
        from . import BDENTAL_Props, BDENTAL_Panel
        from .Operators import BDENTAL_ScanOperators, AlignOperators

        addon_modules = [
            BDENTAL_Props,
            BDENTAL_Panel,
            BDENTAL_ScanOperators,
            AlignOperators,
        ]
        init_classes = []

        ############################################################################################
        # Registration :
        ############################################################################################
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

    else:

        def register():

            message = "Please Check Internet Connexion and restart Blender! "
            print(message)

        def unregister():
            pass

        if __name__ == "__main__":
            register()
