#    Bake to Vertex Color
#    Copyright (C) 2019 Daniel Engler

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import bpy
from bpy.types import Panel
from bpy.types import Operator, PropertyGroup, UIList
from bpy.props import IntProperty, StringProperty

# from .bake import *
# from .imagelist import *
# from .panel import *

bl_info = {
    "name": "Bake to Vertex Color",
    "description": "Transfer Image to selected Vertex Color in all selected Objects",
    "author": "Daniel Engler",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "Shader Editor Toolbar",
    "category": "Node",
}


# TODO average color over sample radius. useful?


########################################################################
# OPERATOR
########################################################################


class BAKETOVERTEXCOLOR_OT_bake(Operator):
    bl_idname = "object.baketovertexcolor_bake"
    bl_label = "Transfer to Vertex Color"
    bl_description = "Transfer Image to selected Vertex Color in all selected Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        img_index = context.scene.baketovertexcolor_imagelist_index
        img = bpy.data.images[img_index]

        if not img:
            self.report({'ERROR'}, f"No image: {img.name}")
            return {'CANCELLED'}

        if not img.has_data:
            self.report({'ERROR'}, f"No image data: {img.name}")
            return {'CANCELLED'}

        w = img.size[0]
        h = img.size[1]

        for obj in context.selected_objects:

            vert_index = obj.data.vertex_colors.active_index
            vert_values = obj.data.vertex_colors[vert_index].data.values()

            uv_index = obj.data.uv_layers.active_index
            uv_layer = obj.data.uv_layers[uv_index]

            for i, vert in enumerate(uv_layer.data.values()):

                x, y = vert.uv
                x = int(x * w) % w
                y = int(y * h) % h
                p = 4 * (x + w * y)

                color = [img.pixels[p],
                         img.pixels[p+1],
                         img.pixels[p+2],
                         img.pixels[p+3]]

                vert_values[i].color = color

        return {'FINISHED'}


########################################################################
# LIST
########################################################################


class BAKETOVERTEXCOLOR_ImageListItem(PropertyGroup):
    image: StringProperty(name="Image")


class BAKETOVERTEXCOLOR_UL_ImageList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name)


class BAKETOVERTEXCOLOR_ImageList_OT_Init(Operator):
    """Load/Update Image List"""

    bl_idname = "baketovertexcolor_imagelist.init"
    bl_label = "Load/Update"

    def execute(self, context):
        image_list = context.scene.baketovertexcolor_imagelist

        if image_list:
            bpy.ops.baketovertexcolor_imagelist.delete()

        if not len(image_list):
            for name, image in bpy.data.images.items():
                item = image_list.add()
                item.name = name

        return{'FINISHED'}


class BAKETOVERTEXCOLOR_ImageList_OT_Delete(Operator):
    bl_idname = "baketovertexcolor_imagelist.delete"
    bl_label = "Clear"

    @classmethod
    def poll(cls, context):
        return context.scene.baketovertexcolor_imagelist

    def execute(self, context):
        baketovertexcolor_imagelist = context.scene.baketovertexcolor_imagelist.clear()
        return{'FINISHED'}


# class BAKETOVERTEXCOLOR_ImageList_OT_Reset(Operator):
#     """Reset list to default values"""

#     bl_idname = "baketovertexcolor_imagelist.reset"
#     bl_label = "Update"

#     def execute(self, context):
#         if context.scene.baketovertexcolor_imagelist:
#             bpy.ops.baketovertexcolor_imagelist.delete()
#             bpy.ops.baketovertexcolor_imagelist.init()

#         return{'FINISHED'}


########################################################################
# PANEL
########################################################################


class BAKETOVERTEXCOLOR_PT_SubPanel(Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = 'UI'
    bl_context = "objectmode"
    bl_label = "Subpanel"

    def draw(self, context):
        pass


class BAKETOVERTEXCOLOR_PT_Main(Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_label = "Bake to Vertex Color"
    bl_context = "objectmode"
    bl_category = "Bake to Vertex Color"

    @classmethod
    def poll(cls, context):
        if context.space_data.tree_type == 'ShaderNodeTree':
            return True
        return False

    def draw(self, context):

        col = self.layout
        col.operator('object.baketovertexcolor_bake')
        col.label(text="Image List:")
        col.template_list("BAKETOVERTEXCOLOR_UL_ImageList", "Image_List", context.scene,
                          "baketovertexcolor_imagelist",
                          context.scene, "baketovertexcolor_imagelist_index")
        row = col.row(align=True)
        row.operator('baketovertexcolor_imagelist.init')
        # row.operator('baketovertexcolor_imagelist.reset')
        row.operator('baketovertexcolor_imagelist.delete')


########################################################################
# REGISTER
########################################################################

classes = (
    BAKETOVERTEXCOLOR_ImageListItem,
    BAKETOVERTEXCOLOR_UL_ImageList,
    BAKETOVERTEXCOLOR_ImageList_OT_Init,
    BAKETOVERTEXCOLOR_ImageList_OT_Delete,
    # BAKETOVERTEXCOLOR_ImageList_OT_Reset,
    BAKETOVERTEXCOLOR_PT_SubPanel,
    BAKETOVERTEXCOLOR_PT_Main,
    BAKETOVERTEXCOLOR_OT_bake
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.baketovertexcolor_imagelist = bpy.props.CollectionProperty(
        type=BAKETOVERTEXCOLOR_ImageListItem)
    bpy.types.Scene.baketovertexcolor_imagelist_index = bpy.props.IntProperty(
        name="Imagelist Index", default=0)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.baketovertexcolor_imagelist_index


if __name__ == "__main__":
    register()
