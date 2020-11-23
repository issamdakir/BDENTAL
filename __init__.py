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
    "blender": (2, 90, 1),  ################# Blender working version
    "location": "3D View -> UI SIDE PANEL ",
    "description": "3D Tools suite for Digital Dentistry",  ########### Addon description
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Dental",  ################## Addon category
}
#############################################################################################
# IMPORTS :
#############################################################################################
# Python imports :
import sys, os, bpy

#############################################################
# Add sys Paths : Addon directory and requirements directory
addon_dir = os.path.dirname(os.path.abspath(__file__))
requirements_path = os.path.join(addon_dir, "Resources\\Requirements")

sysPaths = [addon_dir, requirements_path]

for path in sysPaths:
    if not path in sys.path:
        sys.path.append(path)
###############################################################
# Addon modules imports :
from . import BDENTAL_Props, BDENTAL_Panel
from .Operators import BDENTAL_ScanOperators

############################################################################################
# Registration :
############################################################################################

addon_modules = [
    BDENTAL_Props,
    BDENTAL_Panel,
    BDENTAL_ScanOperators,
]

init_classes = []


# Registration :
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
