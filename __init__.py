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
import bpy.utils.previews
from bpy.props import BoolProperty, EnumProperty, IntProperty
from bpy.types import Operator, Panel, WindowManager
import numpy as np

bl_info = {
    "name": "Bake to Vertex Color",
    "description": "Transfer Image to selected Vertex Color in all selected Objects",
    "author": "Daniel Engler",
    "version": (0, 0, 8),
    "blender": (2, 82, 0),
    "location": "Shader Editor Toolbar",
    "category": "Node",
}


########################################################################
# OPERATOR
########################################################################


def pick_color(vert, pixels, img_width, img_height, radius, diameter, mask=None, mask_sum=1):

    # x and y flipped
    x = int(vert.uv[1] * img_height) % img_height
    y = int(vert.uv[0] * img_width) % img_width

    if mask is None:
        return pixels[x, y]
    else:
        x_top = (x + 1 - radius) % img_height
        y_top = (y + 1 - radius) % img_width

        # Slice of Pixel
        pixel_slice = pixels[x_top:x_top + diameter, y_top:y_top + diameter, :]

        # apply mask
        pixel_slice = mask * pixel_slice

        color_avg = np.zeros(4)

        color_avg[0] = pixel_slice[:, :, 0:1].sum()
        color_avg[1] = pixel_slice[:, :, 1:2].sum()
        color_avg[2] = pixel_slice[:, :, 2:3].sum()
        color_avg[3] = pixel_slice[:, :, 3:4].sum()

        color_avg = color_avg / mask_sum

        return color_avg


class BAKETOVERTEXCOLOR_OT_bake(Operator):
    bl_idname = "object.baketovertexcolor_bake"
    bl_label = "Transfer to Vertex Color"
    bl_description = "Transfer Image to selected Vertex Color in all selected Objects"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        wm = context.window_manager

        img_name = bpy.data.window_managers["WinMan"].baketovertexcolor_previews
        img = bpy.data.images[img_name]

        if not img:
            self.report({'ERROR'}, f"No image")
            return {'CANCELLED'}

        img_width = img.size[0]
        img_height = img.size[1]

        if img_width == 0 or img_height == 0:
            self.report({'ERROR'}, f"No image data! Image Size = 0: {img.name}")
            return {'CANCELLED'}

        r = wm.baketovertexcolor_sample_radius
        d = 2 * r - 1

        if d - 1 > img_width or d - 1 > img_height:
            self.report({'ERROR'}, "Sample radius too large")
            return {'CANCELLED'}

        pixels = np.array(img.pixels).reshape(img_height, img_width, 4)

        # Overdraw pixels:
        pixels_bottom = pixels[0:2 * r, :, :]
        pixels = np.concatenate((pixels, pixels_bottom), axis=0)
        pixels_side = pixels[:, 0:2 * r, :]
        pixels = np.concatenate((pixels, pixels_side), axis=1)

        # Mask - defines the shape of the "color picker"
        if r == 1:
            mask = None
            mask_sum = 1
        else:
            if wm.baketovertexcolor_use_sample_circle:
                # Circle mask:
                # quarter piece for the 2D-mask
                mask_2d = np.fromfunction(lambda i, j: i ** 2 + j ** 2, (r, r), dtype=int)

                # condition r**2 - r gives better circle shape, than r**2
                mask_2d[mask_2d >= r ** 2 - r] = 0
                mask_2d[mask_2d > 1] = 1
                mask_2d[0] = 1

                # puzzle the full 2D-mask from the quarter piece
                mask_2d = np.rot90(mask_2d, -2)
                mask_2d = np.concatenate((mask_2d, np.fliplr(mask_2d[:, 0:r - 1])), axis=1)
                mask_2d = np.concatenate((mask_2d, np.flipud(mask_2d[0:r - 1, :])), axis=0)

                # divisor for average color
                mask_sum = mask_2d.sum()

                # the final mask is 3-dimentional for the 4 color channels
                mask = np.zeros((d, d, 4))
                mask[mask_2d > 0] = 1
            else:
                # Square mask:
                mask = np.ones((d, d, 4))
                mask_sum = d**2

        # to restore object selections
        orig_active_object = context.active_object
        orig_selected_object = context.selected_objects
        for obj in orig_selected_object:
            obj.select_set(False)

        for obj in orig_selected_object:
            # temp. set to active for bpy.ops.mesh.vertex_color_add()
            bpy.context.view_layer.objects.active = obj

            # Skip, if UV Map is missing
            if len(obj.data.uv_layers) <= 0:
                self.report({'INFO'}, f"UV Map missing on {obj.name}")
                continue

            if len(obj.data.vertex_colors) == 0:
                bpy.ops.mesh.vertex_color_add()
            else:
                if not wm.baketovertexcolor_overwrite:
                    # Skip, if Vertex Color max count reached
                    if len(obj.data.vertex_colors) == 8:
                        self.report({'INFO'}, f"Vertex Colors maximum count reached on {obj.name}")
                        continue
                    else:
                        bpy.ops.mesh.vertex_color_add()

            uv_index = obj.data.uv_layers.active_index
            uv_layer = obj.data.uv_layers[uv_index]

            vert_index = obj.data.vertex_colors.active_index
            vert_values = obj.data.vertex_colors[vert_index].data.values()

            for i, vert in enumerate(uv_layer.data.values()):
                vert_values[i].color = pick_color(vert, pixels, img_width, img_height, r, d, mask=mask, mask_sum=mask_sum)

            obj.select_set(False)

        # restore object selections
        for obj in orig_selected_object:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = orig_active_object

        return {'FINISHED'}


########################################################################
# IMAGE LIST
########################################################################


preview_collections = {}


def enum_previews_image_items(self, context):

    enum_items = []

    if context is None:
        return enum_items

    prev_coll = preview_collections["main"]

    for i, img in enumerate(bpy.data.images.values()):
        name = img.name
        thumb = img.preview
        enum_items.append((name, name, "", thumb.icon_id, i))

    prev_coll.baketovertexcolor_previews = enum_items
    return prev_coll.baketovertexcolor_previews


########################################################################
# PANEL
########################################################################


class BAKETOVERTEXCOLOR_PT_Main(Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_label = "Bake to Vertex Color"
    bl_context = "objectmode"
    bl_category = "Bake to Vertex Color"

    # @classmethod
    # def poll(cls, context):
    #     if context.space_data.tree_type == 'ShaderNodeTree':
    #         return True
    #     return False

    def draw(self, context):

        layout = self.layout
        wm = context.window_manager

        layout.operator('object.baketovertexcolor_bake')
        layout.prop(wm, 'baketovertexcolor_overwrite')
        layout.prop(wm, 'baketovertexcolor_sample_radius')
        layout.prop(wm, 'baketovertexcolor_use_sample_circle')

        row = layout.row()
        row.template_icon_view(wm, "baketovertexcolor_previews")

        row = layout.row()
        row.prop(wm, "baketovertexcolor_previews", text="")


########################################################################
# MAIN & REGISTER
########################################################################

classes = (
    BAKETOVERTEXCOLOR_PT_Main,
    BAKETOVERTEXCOLOR_OT_bake
)


def register():

    WindowManager.baketovertexcolor_previews = EnumProperty(
        items=enum_previews_image_items,
    )

    prev_coll = bpy.utils.previews.new()
    prev_coll.baketovertexcolor_previews = ()

    preview_collections["main"] = prev_coll

    WindowManager.baketovertexcolor_overwrite = BoolProperty(
        name="Overwrite",
        description="Overwrite selected Vertex Color",
        default=True
    )

    WindowManager.baketovertexcolor_sample_radius = IntProperty(
        name="Sample Radius",
        description="Average Color over square sample",
        default=1,
        min=1,
        soft_max=5,
    )

    WindowManager.baketovertexcolor_use_sample_circle = BoolProperty(
        name="Circle Sample Shape",
        description="The shape of sampled colors is a circle (not a square)",
        default=False
    )

    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    del WindowManager.baketovertexcolor_previews

    for prev_coll in preview_collections.values():
        bpy.utils.previews.remove(prev_coll)
    preview_collections.clear()

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
