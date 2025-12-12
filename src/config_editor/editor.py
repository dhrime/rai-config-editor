import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox, simpledialog
import math
import os
import random

from .constants import *
from .models import LevelObject
from .io_utils import parse_g_file, generate_g_string

class EditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RAI Config Editor")
        
        # --- FIX: Force a large default window size ---
        self.root.geometry("1200x950")
        
        # World State
        self.world_w = DEFAULT_WORLD_SIZE
        self.world_h = DEFAULT_WORLD_SIZE
        self.base_file = DEFAULT_BASE_FILE
        self.camera_str = DEFAULT_CAMERA
        
        # Viewport State (Dynamic)
        self.canvas_w = DEFAULT_WINDOW_SIZE
        self.canvas_h = DEFAULT_WINDOW_SIZE
        self.ppm = 100 # Pixels Per Meter (Calculated dynamically)
        self.offset_x = 0
        self.offset_y = 0

        self.goal_index = 0
        self.clipboard = None 
        self.mouse_x_px = 0
        self.mouse_y_px = 0

        # UI Layout
        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        toolbar = tk.Frame(main_frame, height=40)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Canvas - Background set to VOID color
        # Note: 'width' and 'height' here are just requests; 
        # pack(expand=True) + root.geometry() determines actual size.
        self.canvas = tk.Canvas(main_frame, bg=COLOR_VOID, width=DEFAULT_WINDOW_SIZE, height=DEFAULT_WINDOW_SIZE)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Handle Window Resizing
        self.canvas.bind("<Configure>", self.on_resize)
        
        # Mouse Bindings
        self.canvas.bind("<Button-1>", self.on_bg_click)
        self.canvas.bind("<Button-2>", self.on_canvas_right_click) 
        self.canvas.bind("<Button-3>", self.on_canvas_right_click) 
        self.canvas.bind("<Motion>", self.track_mouse)
        
        prop_panel = tk.Frame(main_frame, width=200, bg="#cccccc", padx=10, pady=10)
        prop_panel.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Toolbar Buttons
        pad = 5
        tk.Button(toolbar, text="NEW", command=self.new_file, bg="#ffdddd").pack(side=tk.LEFT, padx=(0, 15))
        tk.Button(toolbar, text="Wall", command=lambda: self.add_obj("wall", 0.1, 1.5, "wall", "brown")).pack(side=tk.LEFT, padx=pad)
        tk.Button(toolbar, text="Obstacle", command=lambda: self.add_obj("obs", 0.3, 1.2, "movable", "#ffffff")).pack(side=tk.LEFT, padx=pad)
        tk.Button(toolbar, text="Goal Pair", command=self.add_goal_pair, bg="#e6e6fa").pack(side=tk.LEFT, padx=pad)
        tk.Button(toolbar, text="Agent", command=lambda: self.add_obj("ego", 0.4, 0.4, "agent", "yellow")).pack(side=tk.LEFT, padx=pad)
        
        tk.Button(toolbar, text="Save .g", command=self.save_file).pack(side=tk.RIGHT, padx=pad)
        tk.Button(toolbar, text="Load .g", command=self.load_file).pack(side=tk.RIGHT, padx=pad)

        # Properties Panel
        tk.Label(prop_panel, text="Selection", font=("Arial", 11, "bold"), bg="#cccccc").pack(pady=10)
        self.lbl_name = tk.Label(prop_panel, text="None", bg="#cccccc")
        self.lbl_name.pack()
        self.lbl_dims = tk.Label(prop_panel, text="-", bg="#cccccc")
        self.lbl_dims.pack(pady=(10,0))
        self.lbl_pos = tk.Label(prop_panel, text="-", bg="#cccccc")
        self.lbl_pos.pack(pady=(10,0))
        
        # Context Menu
        self.context_menu = tk.Menu(root, tearoff=0)
        self.context_menu.add_command(label="Rename", command=self.rename_selection)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Cut", command=self.cut_selection)
        self.context_menu.add_command(label="Copy", command=self.copy_selection)
        self.context_menu.add_command(label="Paste", command=self.paste_selection)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Change Color", command=self.change_color)
        self.context_menu.add_command(label="Delete", command=self.delete_selected)

        # Shortcuts
        for k in ["<Control-c>", "<Command-c>"]: root.bind(k, lambda e: self.copy_selection())
        for k in ["<Control-v>", "<Command-v>"]: root.bind(k, lambda e: self.paste_selection())
        for k in ["<Control-x>", "<Command-x>"]: root.bind(k, lambda e: self.cut_selection())
        for k in ["<Delete>", "<BackSpace>"]: root.bind(k, lambda e: self.delete_selected())
        root.bind("<F2>", lambda e: self.rename_selection())
        
        root.bind("<Left>", lambda e: self.nudge(-0.01, 0))
        root.bind("<Right>", lambda e: self.nudge(0.01, 0))
        root.bind("<Up>", lambda e: self.nudge(0, 0.01))
        root.bind("<Down>", lambda e: self.nudge(0, -0.01))

        self.last_click_pos = (0, 0)
        self.objects = []
        self.obj_counter = 0
        self.selected_obj = None
        self.link_lines = []

        # Trigger initial calculation
        self.update_scaling_constants()

    # --- RESPONSIVE LOGIC ---
    def on_resize(self, event):
        # Called whenever the window is resized (including on startup)
        self.canvas_w = event.width
        self.canvas_h = event.height
        self.update_scaling_constants()
        self.redraw_all()

    def update_scaling_constants(self):
        # We add padding equal to 2x Wall Thickness (0.2m) + small margin
        margin_world = 0.25 
        
        # Calculate Pixels Per Meter based on the SMALLER dimension
        ppm_w = self.canvas_w / (self.world_w + margin_world)
        ppm_h = self.canvas_h / (self.world_h + margin_world)
        
        self.ppm = min(ppm_w, ppm_h)
        self.offset_x = self.canvas_w / 2
        self.offset_y = self.canvas_h / 2

    def redraw_all(self):
        self.draw_environment()
        for obj in self.objects:
            obj.update_visuals()
            self.canvas.tag_raise(obj.rect_id)
            self.canvas.tag_raise(obj.text_id)
            self.canvas.tag_raise(f"{obj.name}_handle")
        self.draw_links()

    def draw_environment(self):
        self.canvas.delete("background")
        
        # Calculate floor rect dimensions in pixels
        fw_px = self.world_w * self.ppm
        fh_px = self.world_h * self.ppm
        
        # Center points
        fx1 = self.offset_x - (fw_px / 2)
        fy1 = self.offset_y - (fh_px / 2)
        fx2 = fx1 + fw_px
        fy2 = fy1 + fh_px
        
        # Floor
        self.canvas.create_rectangle(fx1, fy1, fx2, fy2, fill=COLOR_FLOOR, outline="black", tags="background")
        
        # Grid
        steps = int(self.world_w)
        # Vertical
        for i in range(steps + 1):
            ratio = i / steps
            x = fx1 + (ratio * fw_px)
            self.canvas.create_line(x, fy1, x, fy2, fill="#888", width=1, dash=(2, 4), tags="background")
        # Horizontal
        for i in range(steps + 1):
            ratio = i / steps
            y = fy1 + (ratio * fh_px)
            self.canvas.create_line(fx1, y, fx2, y, fill="#888", width=1, dash=(2, 4), tags="background")

        # Axes
        self.canvas.create_line(self.offset_x, fy1, self.offset_x, fy2, fill="#444", width=2, tags="background")
        self.canvas.create_line(fx1, self.offset_y, fx2, self.offset_y, fill="#444", width=2, tags="background")

        # Walls (Hug the floor EXACTLY)
        wall_thick_px = 0.1 * self.ppm 
        
        # Top
        self.canvas.create_rectangle(fx1 - wall_thick_px, fy1 - wall_thick_px, fx2 + wall_thick_px, fy1, fill=COLOR_WALL_BASE, outline="black", tags="background")
        # Bottom
        self.canvas.create_rectangle(fx1 - wall_thick_px, fy2, fx2 + wall_thick_px, fy2 + wall_thick_px, fill=COLOR_WALL_BASE, outline="black", tags="background")
        # Left
        self.canvas.create_rectangle(fx1 - wall_thick_px, fy1, fx1, fy2, fill=COLOR_WALL_BASE, outline="black", tags="background")
        # Right
        self.canvas.create_rectangle(fx2, fy1, fx2 + wall_thick_px, fy2, fill=COLOR_WALL_BASE, outline="black", tags="background")

    # --- Logic methods ---
    def track_mouse(self, event):
        self.mouse_x_px = event.x
        self.mouse_y_px = event.y

    def get_next_name(self, base_name):
        existing_nums = []
        for obj in self.objects:
            if obj.name.startswith(base_name):
                suffix = obj.name[len(base_name):]
                if suffix.isdigit(): existing_nums.append(int(suffix))
                elif suffix.startswith("_") and suffix[1:].isdigit(): existing_nums.append(int(suffix[1:]))
        next_num = 1
        if existing_nums: next_num = max(existing_nums) + 1
        return f"{base_name}{next_num}"

    def get_random_color(self):
        r = lambda: random.randint(50,200) 
        return '#%02X%02X%02X' % (r(),r(),r())

    def add_obj(self, base_name, w, h, otype, color, x=0, y=0, name_override=None, linked=None):
        name = name_override if name_override else self.get_next_name(base_name)
        obj = LevelObject(self.canvas, name, x, y, w, h, otype, color, self, linked_obj=linked)
        self.objects.append(obj)
        self.select_object(obj)
        return obj

    def add_goal_pair(self):
        base_id = 1
        while True:
            n1 = f"obj{base_id}"
            n2 = f"goal{base_id}"
            exists = any(o.name == n1 or o.name == n2 for o in self.objects)
            if not exists: break
            base_id += 1
        
        c = self.get_random_color()
        obj = self.add_obj(f"obj{base_id}", 0.3, 0.3, "goal_object", c, x=-0.5, y=0, name_override=f"obj{base_id}")
        goal = self.add_obj(f"goal{base_id}", 0.3, 0.3, "goal_location", c, x=0.5, y=0, name_override=f"goal{base_id}", linked=obj)
        obj.linked_obj = goal
        self.select_object(obj)

    def draw_links(self):
        self.canvas.delete("link_line")
        if self.selected_obj and self.selected_obj.linked_obj:
            o1 = self.selected_obj
            o2 = self.selected_obj.linked_obj
            x1, y1 = o1.world_to_pixel(o1.x, o1.y)
            x2, y2 = o2.world_to_pixel(o2.x, o2.y)
            self.canvas.create_line(x1, y1, x2, y2, fill="black", dash=(4, 4), tags="link_line")

    def select_object(self, obj):
        if self.selected_obj and self.selected_obj != obj:
            self.selected_obj.deselect()
        self.selected_obj = obj
        self.selected_obj.select()
        self.draw_links()
        self.update_properties_panel()
        
    def show_context_menu(self, event):
        self.last_click_pos = (event.x, event.y)
        state_paste = "normal" if self.clipboard else "disabled"
        self.context_menu.entryconfig("Paste", state=state_paste)
        self.context_menu.post(event.x_root, event.y_root)

    def on_canvas_right_click(self, event):
        self.on_bg_click(event)
        self.show_context_menu(event)

    def change_color(self):
        if not self.selected_obj: return
        color = colorchooser.askcolor(title="Choose color")[1]
        if color:
            self.selected_obj.color = color
            self.selected_obj.update_visuals()
            if self.selected_obj.linked_obj:
                self.selected_obj.linked_obj.color = color
                self.selected_obj.linked_obj.update_visuals()

    def rename_selection(self):
        if not self.selected_obj: return
        new_name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=self.selected_obj.name)
        if new_name:
            self.selected_obj.name = new_name
            self.selected_obj.update_visuals()
            self.update_properties_panel()

    def copy_selection(self):
        if self.selected_obj:
            self.clipboard = {
                'w': self.selected_obj.width,
                'h': self.selected_obj.height,
                'type': self.selected_obj.obj_type,
                'color': self.selected_obj.color,
                'base_name': self.selected_obj.name.rstrip('0123456789').rstrip('_')
            }

    def cut_selection(self):
        if self.selected_obj:
            self.copy_selection()
            self.delete_selected()

    def paste_selection(self):
        if self.clipboard:
            if self.last_click_pos == (0,0) and self.selected_obj: 
                new_x = self.selected_obj.x + 0.2
                new_y = self.selected_obj.y - 0.2
            elif self.mouse_x_px != 0: 
                wx = (self.mouse_x_px - self.offset_x) / self.ppm
                wy = -(self.mouse_y_px - self.offset_y) / self.ppm
                new_x, new_y = wx, wy
            else:
                new_x, new_y = 0.2, 0.2

            self.add_obj(
                self.clipboard['base_name'],
                self.clipboard['w'],
                self.clipboard['h'],
                self.clipboard['type'],
                self.clipboard['color'],
                new_x, new_y
            )

    def nudge(self, dx, dy):
        if self.selected_obj:
            self.selected_obj.x += dx
            self.selected_obj.y += dy
            self.selected_obj.update_visuals()
            self.update_properties_panel()
            self.draw_links()

    def on_bg_click(self, event):
        items = self.canvas.find_overlapping(event.x, event.y, event.x+1, event.y+1)
        if items:
            top_item = items[-1]
            tags = self.canvas.gettags(top_item)
            if "background" in tags:
                if self.selected_obj:
                    self.selected_obj.deselect()
                    self.selected_obj = None
                    self.canvas.delete("link_line")
                    self.lbl_name.config(text="None")
                    self.lbl_dims.config(text="-")
                    self.lbl_pos.config(text="-")

    def delete_selected(self):
        if not self.selected_obj: return
        target = self.selected_obj
        partner = target.linked_obj
        
        if target.obj_type == "goal_object":
            if partner: self.delete_specific_object(partner)
        elif target.obj_type == "goal_location":
            if partner: partner.linked_obj = None
                
        self.delete_specific_object(target)
        self.selected_obj = None
        self.canvas.delete("link_line")
        self.lbl_name.config(text="None")

    def delete_specific_object(self, obj):
        self.canvas.delete(obj.rect_id)
        self.canvas.delete(obj.text_id)
        for hid in obj.handles.values(): self.canvas.delete(hid)
        if obj in self.objects: self.objects.remove(obj)

    def update_properties_panel(self):
        if self.selected_obj:
            o = self.selected_obj
            self.lbl_name.config(text=o.name)
            self.lbl_dims.config(text=f"W: {round(o.width,2)}\nH: {round(o.height,2)}")
            self.lbl_pos.config(text=f"X: {round(o.x,2)}\nY: {round(o.y,2)}")

    def new_file(self):
        self.canvas.delete("all")
        self.objects = []
        self.selected_obj = None
        self.draw_environment()
        self.lbl_name.config(text="None")
        self.root.title("RAI Config Editor - Untitled")

    def save_file(self):
        content = generate_g_string(self.objects, self.base_file, self.camera_str)
        file_path = filedialog.asksaveasfilename(defaultextension=".g", filetypes=[("RAI Config", "*.g")])
        if file_path:
            with open(file_path, "w") as f:
                f.write(content)
            self.root.title(f"RAI Config Editor - {os.path.basename(file_path)}")

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("RAI Config", "*.g")])
        if not file_path: return
        self.new_file()
        self.root.title(f"RAI Config Editor - {os.path.basename(file_path)}")
        
        with open(file_path, "r") as f:
            content = f.read()
            
        objs, base_file = parse_g_file(content)
        self.base_file = base_file
        
        loaded_objects = []
        for data in objs:
            new_obj = self.add_obj(data['name'], data['w'], data['h'], data['type'], data['color'], data['x'], data['y'], name_override=data['full_name'])
            loaded_objects.append(new_obj)

        goals = [o for o in loaded_objects if o.obj_type == "goal_location"]
        objs_g = [o for o in loaded_objects if o.obj_type == "goal_object"]
        for g in goals:
            for o in objs_g:
                if g.color == o.color and not g.linked_obj and not o.linked_obj:
                    g.linked_obj = o
                    o.linked_obj = g
                    break