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

Wmin, Wmax  = -400, 3000
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
        

        # Draw Addon UI :

        layout = self.layout
        # row = layout.row()
        # row.operator("bdental.addplanes", icon="COLORSET_03_VEC")
        row = layout.row()
        row.prop(BDENTAL_Props, "UserProjectDir", text="Project Directory")

        if BDENTAL_Props.UserProjectDir:
            row = layout.row()
            row.prop(BDENTAL_Props, "DataType")

            if BDENTAL_Props.DataType == "DICOM Series":
                row = layout.row()
                row.prop(BDENTAL_Props, "UserDcmDir", text="DICOM Folder")
                if BDENTAL_Props.UserDcmDir:

                    Box = layout.box()
                    row = Box.row()
                    row.alignment = "CENTER"
                    row.scale_y = 2
                    row.operator(
                        "bdental.volume_render", icon="OUTLINER_OB_POINTCLOUD"
                    )
                    
                    row = layout.row()
                    row.label(text=f"Threshold {Wmin} to {Wmax} HU:")
                    row = layout.row()
                    row.prop(
                        BDENTAL_Props, "Treshold", text="TRESHOLD", slider=True
                    )

                    row = layout.row()
                    row.operator("bdental.tresh_segment")
                    row = layout.row()
                    row.operator("bdental.addslices", icon="EMPTY_AXIS")


            if BDENTAL_Props.DataType == "3D Image File":

                row = layout.row()
                row.prop(BDENTAL_Props, "UserImageFile", text="File Path")

                if BDENTAL_Props.UserImageFile:
                    
                    row = layout.row()
                    row.alignment = "CENTER"
                    row.scale_y = 2
                    row.operator(
                        "bdental.volume_render",icon="OUTLINER_OB_POINTCLOUD"
                    )
                    row = layout.row()
                    row.label(text=f"TRESHOLD {Wmin}/{Wmax} :")
                    row.operator("bdental.tresholdupdate")
                    row = layout.row()
                    row.prop(
                        BDENTAL_Props, "Treshold", text="TRESHOLD", slider=True
                    )
                    
                    row = layout.row()
                    row.operator("bdental.tresh_segment")
                    row = layout.row()
                    row.operator("bdental.addslices", icon="EMPTY_AXIS")

                
                    


class BDENTAL_PT_AlignPanel(bpy.types.Panel):
    """ BLENDER DENTAL SCAN VIEWER"""

    bl_idname = "BDENTAL_PT_AlignPanel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"  # blender 2.7 and lower = TOOLS
    bl_category = "BDENT"
    bl_label = "BDENTAL ALIGN TOOLS :"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        BDENTAL_Props = context.scene.BDENTAL_Props
        AlignModalState = BDENTAL_Props.AlignModalState
        layout = self.layout
        row = layout.row()
        row.operator("bdental.alignpoints")
        row.operator("bdental.alignpointsinfo", text="", icon="INFO")

        # conditions :
        ###################################
        if not bpy.context.selected_objects:
            self.AlignLabels = "NOTREADY"
            BaseObjectLabel = " Empty !"
            BaseObjectIcon = red_icon
            AlignObjectLabel = " Empty !"
            AlignObjectIcon = red_icon

        if len(bpy.context.selected_objects) == 1:
            self.AlignLabels = "NOTREADY"
            BaseObject = bpy.context.selected_objects[0]
            BaseObjectLabel = f" {BaseObject.name}"
            BaseObjectIcon = green_icon
            AlignObjectLabel = " Empty ! "
            AlignObjectIcon = red_icon

        if len(bpy.context.selected_objects) == 2:
            self.AlignLabels = "GOOD"
            BaseObject = bpy.context.active_object
            AlignObject = [
                obj
                for obj in bpy.context.selected_objects
                if not obj is bpy.context.active_object
            ][0]
            BaseObjectLabel = f" {BaseObject.name}"
            BaseObjectIcon = green_icon
            AlignObjectLabel = f" {AlignObject.name}"
            AlignObjectIcon = orange_icon

        Condition_1 = len(bpy.context.selected_objects) != 2
        Condition_2 = bpy.context.selected_objects and not bpy.context.active_object
        Condition_3 = bpy.context.selected_objects and not (
            bpy.context.active_object in bpy.context.selected_objects
        )
        Condition_4 = not bpy.context.active_object in bpy.context.visible_objects

        if Condition_1 or Condition_2 or Condition_3 or Condition_4:
            self.AlignLabels = "INVALID"
        if AlignModalState:
            self.AlignLabels = "MODAL"

        #########################################

        if self.AlignLabels == "GOOD":

            box = layout.box()

            row = box.row()
            row.label(text=f"BASE object  :{BaseObjectLabel}")  # , icon=BaseObjectIcon
            row = box.row()
            row.label(
                text=f"ALIGN object :{AlignObjectLabel}"
            )  # , icon=AlignObjectIcon
            row = box.row()
            row.alert = True
            row.label(text="READY FOR ALIGNEMENT.")

        if self.AlignLabels == "NOTREADY":

            box = layout.box()

            # row = box.row()
            # row.label(text=f"BASE object  :{BaseObjectLabel}", icon=BaseObjectIcon)
            # row = box.row()
            # row.label(text=f"ALIGN object :{AlignObjectLabel}", icon=AlignObjectIcon)
            row = box.row()
            row.alert = True
            row.label(text="NOT READY!")

        if self.AlignLabels == "INVALID":
            box = layout.box()
            row = box.row()
            row.alert = True
            row.label(text="Invalid objects selection, check info !", icon="ERROR")

        if self.AlignLabels == "MODAL":
            box = layout.box()
            row = box.row()
            row.alert = True
            row.label(text="WAITING FOR ALIGNEMENT...!")

        row = layout.row()
        row.operator("bdental.alignicp")
        # if self.AlignLabels == "GOOD":
        #     row = layout.row()
        #     row.operator("bdental.alignpoints")


#################################################################################################
# Registration :
#################################################################################################

classes = [
    BDENTAL_PT_SCAN_VIEWER,
    BDENTAL_PT_AlignPanel,
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