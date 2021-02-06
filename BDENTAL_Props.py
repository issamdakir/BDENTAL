import bpy
from os.path import abspath

from bpy.props import (
    StringProperty,
    IntProperty,
    FloatProperty,
    EnumProperty,
    FloatVectorProperty,
    BoolProperty,
)



class BDENTAL_Props(bpy.types.PropertyGroup):

    #####################
    #############################################################################################
    # CT_Scan props :
    #############################################################################################
    #####################
    
    UserProjectDir: StringProperty(
        name="Project Directory Path",
        default="",
        description="Project Directory Path",
        subtype="DIR_PATH",
    )

    #####################

    UserDcmDir: StringProperty(
        name="DICOM Path",
        default="",
        description="DICOM Directory Path",
        subtype="DIR_PATH",
    )

    UserImageFile: StringProperty(
        name="User 3D Image File Path",
        default="",
        description="User Image File Path",
        subtype="FILE_PATH",
    )

    #####################

    Data_Types = ["DICOM Series", "3D Image File", ""]
    items = []
    for i in range(len(Data_Types)):
        item = (str(Data_Types[i]), str(Data_Types[i]), str(""), int(i))
        items.append(item)

    DataType: EnumProperty(items=items, description="Data type", default="DICOM Series")

    #######################

    DcmInfo: StringProperty(
        name="(str) DicomInfo",
        default="",
        description="Dicom series files list",
    )
    #######################

    PngDir: StringProperty(
        name="Png Directory",
        default="",
        description=" PNG files Sequence Directory Path",
    )
    #######################

    SlicesDir: StringProperty(
        name="Slices Directory",
        default="",
        description="Slices PNG files Directory Path",
    )
    #######################

    NrrdHuPath: StringProperty(
        name="NrrdHuPath",
        default="",
        description="Nrrd image3D file Path",
    )
    Nrrd255Path: StringProperty(
        name="Nrrd255Path",
        default="",
        description="Nrrd image3D file Path",
    )

    #######################

    IcpVidDict: StringProperty(
        name="IcpVidDict",
        default="None",
        description="ICP Vertices Pairs str(Dict)",
    )
    #######################

    Wmin: IntProperty()
    Wmax: IntProperty()

    #######################
    # SoftTissueMode = BoolProperty(description="SoftTissue Mode ", default=False)

    GroupNodeName: StringProperty(
        name="Group shader Name",
        default="",
        description="Group shader Name",
    )

    #######################

    Treshold: IntProperty(
        name="Treshold",
        description="Volume Treshold",
        default=600,
        min=-400,
        max=3000,
        soft_min=-400,
        soft_max=3000,
        step=1,
    )
    Progress_Bar: FloatProperty(
        name="Progress_Bar",
        description="Progress_Bar",
        subtype="PERCENTAGE",
        default=0.0,
        min=0.0,
        max=100.0,
        soft_min=0.0,
        soft_max=100.0,
        step=1,
        precision=1,
    )

    #######################

    CT_Loaded: BoolProperty(description="CT loaded ", default=False)
    CT_Rendered: BoolProperty(description="CT Rendered ", default=False)
    sceneUpdate: BoolProperty(description="scene update ", default=True)
    AlignModalState: BoolProperty(description="Align Modal state ", default=False)

    #######################


#################################################################################################
# Registration :
#################################################################################################

classes = [
    BDENTAL_Props,
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.BDENTAL_Props = bpy.props.PointerProperty(type=BDENTAL_Props)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.BDENTAL_Props


# props examples :

# Axial_Loc: FloatVectorProperty(
#     name="AXIAL location",
#     description="AXIAL location",
#     subtype="TRANSLATION",
#     update=AxialSliceUpdate,
# )
# Axial_Rot: FloatVectorProperty(
#     name="AXIAL Rotation",
#     description="AXIAL Rotation",
#     subtype="EULER",
#     update=AxialSliceUpdate,
# )
################################################
# Str_Prop_Search_1: StringProperty(
#     name="String Search Property 1",
#     default="",
#     description="Str_Prop_Search_1",
# )
# Float Props :
#########################################################################################

# F_Prop_1: FloatProperty(
#     description="Float Property 1 ",
#     default=0.0,
#     min=-200.0,
#     max=200.0,
#     step=1,
#     precision=1,
#     unit="NONE",
#     update=None,
#     get=None,
#     set=None,
# )
#########################################################################################
# # FloatVector Props :
#     ##############################################
#     FloatV_Prop_1: FloatVectorProperty(
#         name="FloatVectorProperty 1", description="FloatVectorProperty 1", size=3
#     )
#########################################################################################
