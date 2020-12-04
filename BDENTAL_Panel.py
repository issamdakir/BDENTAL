import bpy

# Selected icons :
red_icon = "COLORSET_01_VEC"
orange_icon = "COLORSET_02_VEC"
green_icon = "COLORSET_03_VEC"
blue_icon = "COLORSET_04_VEC"
violet_icon = "COLORSET_06_VEC"
yellow_icon = "COLORSET_09_VEC"
yellow_point = "KEYTYPE_KEYFRAME_VEC"
blue_point = "KEYTYPE_BREAKDOWN_VEC"


####################################################################
# // CUTTING TOOLS PANEL //
####################################################################
class BDENTAL_PT_SCAN_VIEWER(bpy.types.Panel):
    """ BLENDER DENTAL SCAN VIEWER"""

    bl_idname = "BDENTAL_PT_SCAN_VIEWER"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"  # blender 2.7 and lower = TOOLS
    bl_category = "BDENT"
    bl_label = "BDENTAL SCAN VIEWER"
    # bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):

        # Model operation property group :
        BDENTAL_Props = context.scene.BDENTAL_Props
        GroupNodeName = BDENTAL_Props.GroupNodeName
        VGS = bpy.data.node_groups.get(GroupNodeName)
        Wmin, Wmax = BDENTAL_Props.Wmin, BDENTAL_Props.Wmax

        # Draw Addon UI :

        layout = self.layout
        row = layout.row()
        row.prop(BDENTAL_Props, "UserProjectDir", text="Project Directory")

        if BDENTAL_Props.UserProjectDir:
            row = layout.row()
            row.prop(BDENTAL_Props, "DataType")

            if BDENTAL_Props.DataType == "DICOM Series":
                # row = layout.row()
                # row.label(text="DICOM Series Folder :")
                row = layout.row()
                row.prop(BDENTAL_Props, "UserDcmDir", text="DICOM Folder")
                if BDENTAL_Props.UserDcmDir:

                    if BDENTAL_Props.PngDir:
                        row = layout.row()
                        row.operator(
                            "bdental.load_dicom_series", icon="COLORSET_03_VEC"
                        )
                        if BDENTAL_Props.CT_Rendered:
                            row = layout.row()
                            row.operator(
                                "bdental.volume_render", icon="COLORSET_03_VEC"
                            )

                            row = layout.row()
                            row.label(text=f"TRESHOLD {Wmin}/{Wmax} :")
                            row = layout.row()
                            row.prop(
                                BDENTAL_Props, "Treshold", text="TRESHOLD", slider=True
                            )
                            row = layout.row()
                            row.operator("bdental.addslices", icon="EMPTY_AXIS")

                            if (
                                context.active_object
                                and context.active_object.type == "MESH"
                            ):
                                obj = context.active_object
                                if "_SLICE" in obj.name:
                                    split = layout.split(align=True)
                                    col = split.column()
                                    col.label(text=f" {obj.name} location:")
                                    row = col.row(align=True)
                                    row.prop(
                                        obj,
                                        "location",
                                        index=0,
                                        text="Location X :",
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj,
                                        "location",
                                        index=1,
                                        text="Location Y :",
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj,
                                        "location",
                                        index=2,
                                        text="Location Z :",
                                    )

                                    col = split.column()
                                    col.label(text=f" {obj.name} rotation:")
                                    row = col.row(align=True)
                                    row.prop(
                                        obj,
                                        "rotation_euler",
                                        index=0,
                                        text="Angle X :",
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj,
                                        "rotation_euler",
                                        index=1,
                                        text="Angle Y :",
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj,
                                        "rotation_euler",
                                        index=2,
                                        text="Angle Z :",
                                    )
                            row = layout.row()
                            row.operator("bdental.tresh_segment")

                        else:
                            row = layout.row()
                            row.operator(
                                "bdental.volume_render", icon="COLORSET_01_VEC"
                            )

                    if not BDENTAL_Props.PngDir:
                        row = layout.row()
                        row.operator(
                            "bdental.load_dicom_series", icon="COLORSET_01_VEC"
                        )

            if BDENTAL_Props.DataType == "3D Image File":

                row = layout.row()
                row.prop(BDENTAL_Props, "UserImageFile", text="File Path")

                if BDENTAL_Props.UserImageFile:
                    if BDENTAL_Props.PngDir:
                        row = layout.row()
                        row.operator(
                            "bdental.load_3dimage_file", icon="COLORSET_03_VEC"
                        )
                        if BDENTAL_Props.CT_Rendered:
                            row = layout.row()
                            row.operator(
                                "bdental.volume_render", icon="COLORSET_03_VEC"
                            )
                            row = layout.row()
                            row.label(text=f"TRESHOLD {Wmin}/{Wmax} :")
                            row = layout.row()
                            row.prop(
                                BDENTAL_Props, "Treshold", text="TRESHOLD", slider=True
                            )
                            row = layout.row()
                            row.operator("bdental.addslices", icon="EMPTY_AXIS")

                            if (
                                context.active_object
                                and context.active_object.type == "MESH"
                            ):
                                obj = context.active_object
                                if "_SLICE" in obj.name:
                                    split = layout.split(align=True)
                                    col = split.column()
                                    col.label(text=f" {obj.name} location:")
                                    row = col.row(align=True)
                                    row.prop(
                                        obj, "location", index=0, text="Location X :"
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj, "location", index=1, text="Location Y :"
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj, "location", index=2, text="Location Z :"
                                    )

                                    col = split.column()
                                    col.label(text=f" {obj.name} rotation:")
                                    row = col.row(align=True)
                                    row.prop(
                                        obj, "rotation_euler", index=0, text="Angle X :"
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj, "rotation_euler", index=1, text="Angle Y :"
                                    )
                                    row = col.row(align=True)
                                    row.prop(
                                        obj, "rotation_euler", index=2, text="Angle Z :"
                                    )

                            row = layout.row()
                            row.operator("bdental.tresh_segment")
                        else:
                            row = layout.row()
                            row.operator(
                                "bdental.volume_render", icon="COLORSET_01_VEC"
                            )

                    if not BDENTAL_Props.PngDir:
                        row = layout.row()
                        row.operator(
                            "bdental.load_3dimage_file", icon="COLORSET_01_VEC"
                        )


#################################################################################################
# Registration :
#################################################################################################

classes = [
    BDENTAL_PT_SCAN_VIEWER,
]


def register():

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


##########################################################
# TreshRamp = VGS.nodes.get("TresholdRamp")
# ColorPresetRamp = VGS.nodes.get("ColorPresetRamp")
# row = layout.row()
# row.label(
#     text=f"Volume Treshold ({BDENTAL_Props.Wmin}/{BDENTAL_Props.Wmax} HU) :"
# )
# row.template_color_ramp(
#     TreshRamp,
#     "color_ramp",
#     expand=True,
# )
# row = layout.row()
# row.prop(BDENTAL_Props, "Axial_Loc", text="AXIAL Location :")
# row = layout.row()
# row.prop(BDENTAL_Props, "Axial_Rot", text="AXIAL Rotation :")