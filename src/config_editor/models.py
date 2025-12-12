import tkinter as tk
from .constants import *

class LevelObject:
    def __init__(self, canvas, name, x, y, width, height, obj_type, color, app, linked_obj=None):
        self.canvas = canvas
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.obj_type = obj_type
        self.color = color
        self.app = app
        self.linked_obj = linked_obj 
        
        self.handles = {}
        
        tags = (self.name, "selectable")
        
        # --- DRAW ---
        if self.obj_type == "goal_location":

            self.rect_id = canvas.create_rectangle(0, 0, 0, 0, fill=COLOR_FLOOR, outline=self.color, width=3, dash=(6, 4), tags=tags)
        elif self.obj_type == "agent":
            self.rect_id = canvas.create_oval(0, 0, 0, 0, fill=color, outline="black", width=2, tags=tags)
        else:
            self.rect_id = canvas.create_rectangle(0, 0, 0, 0, fill=color, outline="black", width=2, tags=tags)
            
        self.text_id = canvas.create_text(0, 0, text=name, fill="black", tags=tags)
        

        for loc in ["nw", "n", "ne", "w", "e", "sw", "s", "se"]:
            hid = canvas.create_rectangle(0, 0, 0, 0, fill="#00ffff", outline="black", tags=(f"{self.name}_handle", "handle"))
            self.canvas.tag_bind(hid, "<Button-1>", lambda e, l=loc: self.on_handle_click(e, l))
            self.canvas.tag_bind(hid, "<B1-Motion>", lambda e, l=loc: self.on_handle_drag(e, l))
            self.handles[loc] = hid
            self.canvas.itemconfigure(hid, state='hidden')

        self.update_visuals()
        

        for item in [self.rect_id, self.text_id]:
            self.canvas.tag_bind(item, "<Button-1>", self.on_body_click)
            self.canvas.tag_bind(item, "<B1-Motion>", self.on_body_drag)
            self.canvas.tag_bind(item, "<Button-2>", self.on_right_click)
            self.canvas.tag_bind(item, "<Button-3>", self.on_right_click)

    def world_to_pixel(self, wx, wy):
        px = (wx * self.app.ppm) + self.app.offset_x
        py = (-wy * self.app.ppm) + self.app.offset_y
        return px, py

    def pixel_to_world(self, px, py):
        wx = (px - self.app.offset_x) / self.app.ppm
        wy = -(py - self.app.offset_y) / self.app.ppm
        return wx, wy

    def update_visuals(self):
        half_w = (self.width / 2) * self.app.ppm
        half_h = (self.height / 2) * self.app.ppm
        cx, cy = self.world_to_pixel(self.x, self.y)
        
        x1, y1 = cx - half_w, cy - half_h
        x2, y2 = cx + half_w, cy + half_h
        
        self.canvas.coords(self.rect_id, x1, y1, x2, y2)
        self.canvas.coords(self.text_id, cx, cy)
        
        if self.obj_type == "goal_location":
             self.canvas.itemconfig(self.rect_id, outline=self.color, fill=COLOR_FLOOR)
        else:
             self.canvas.itemconfig(self.rect_id, fill=self.color)
        
        self.canvas.itemconfig(self.text_id, text=self.name)
        
        hs = 4
        coords = {
            "nw": (x1, y1), "n": (cx, y1), "ne": (x2, y1),
            "w":  (x1, cy),                "e":  (x2, cy),
            "sw": (x1, y2), "s": (cx, y2), "se": (x2, y2)
        }
        for loc, (hx, hy) in coords.items():
            self.canvas.coords(self.handles[loc], hx-hs, hy-hs, hx+hs, hy+hs)

    def select(self):
        if self.obj_type == "goal_location":
            self.canvas.itemconfig(self.rect_id, width=4, dash="") 
        else:
            self.canvas.itemconfig(self.rect_id, width=3, outline="cyan")
        
        for hid in self.handles.values():
            self.canvas.itemconfigure(hid, state='normal')
        self.canvas.tag_raise(f"{self.name}_handle")

    def deselect(self):
        if self.obj_type == "goal_location":
            self.canvas.itemconfig(self.rect_id, width=3, dash=(6, 4))
        else:
            self.canvas.itemconfig(self.rect_id, width=2, outline="black")
        
        for hid in self.handles.values():
            self.canvas.itemconfigure(hid, state='hidden')

    def on_body_click(self, event):
        self._drag_data = {"x": event.x, "y": event.y}
        self.app.select_object(self)
        return "break"

    def on_right_click(self, event):
        self.app.select_object(self)
        self.app.show_context_menu(event)
        return "break"

    def on_body_drag(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        cx, cy = self.world_to_pixel(self.x, self.y)
        cx += dx
        cy += dy
        self.x, self.y = self.pixel_to_world(cx, cy)
        self.update_visuals()
        self.app.update_properties_panel()
        self.app.draw_links()
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_handle_click(self, event, loc):
        self._resize_data = {"x": event.x, "y": event.y, "loc": loc}
        return "break"

    def on_handle_drag(self, event, loc):
        coords = self.canvas.coords(self.rect_id)
        x1, y1, x2, y2 = coords[0], coords[1], coords[2], coords[3]
        mx, my = event.x, event.y
        
        if "w" in loc: x1 = mx
        if "e" in loc: x2 = mx
        if "n" in loc: y1 = my
        if "s" in loc: y2 = my
        
        if x2 - x1 < 10: 
            if "w" in loc: x1 = x2 - 10
            else: x2 = x1 + 10
        if y2 - y1 < 10:
            if "n" in loc: y1 = y2 - 10
            else: y2 = y1 + 10
            
        new_w_px = x2 - x1
        new_h_px = y2 - y1
        new_cx_px = x1 + (new_w_px / 2)
        new_cy_px = y1 + (new_h_px / 2)
        
        self.x, self.y = self.pixel_to_world(new_cx_px, new_cy_px)
        self.width = new_w_px / self.app.ppm
        self.height = new_h_px / self.app.ppm
        self.update_visuals()
        self.app.update_properties_panel()