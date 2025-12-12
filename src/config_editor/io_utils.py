import re

def rgb_to_str(hex_color):
    if hex_color.startswith("#"):
        r = int(hex_color[1:3], 16) / 255.0
        g = int(hex_color[3:5], 16) / 255.0
        b = int(hex_color[5:7], 16) / 255.0
        return f"{round(r,4)} {round(g,4)} {round(b,4)}"
    return "1 1 1"

def parse_color(c_str):
    try:
        clean = c_str.replace('[', '').replace(']', '').replace(',', ' ')
        parts = clean.split()
        if len(parts) >= 3:
            r = int(float(parts[0]) * 255)
            g = int(float(parts[1]) * 255)
            b = int(float(parts[2]) * 255)
            return f"#{r:02x}{g:02x}{b:02x}"
        return "gray"
    except: return "gray"

def generate_g_string(obj):
    x, y = round(obj.x, 3), round(obj.y, 3)
    w, h = round(obj.width, 3), round(obj.height, 3)
    c_str = rgb_to_str(obj.color)

    if obj.obj_type == "wall":
        return f'{obj.name} (world){{ shape:ssBox, Q:"t({x} {y} 0.3)", size:[{w} {h} 0.6 .02], color:[0.69 0.51 0.45], contact: 1 }}'
    elif obj.obj_type == "movable":
        return f'{obj.name}Joint(world){{ Q:[0.0 0.0 0.1] }}\n{obj.name}({obj.name}Joint) {{ shape:ssBox, Q:"t({x} {y} .0)", size:[{w} {h} .2 .02], logical:{{ movable_o }}, color:[{c_str}], joint:rigid, contact: 1 }}'
    elif obj.obj_type == "goal_object":
            return f'{obj.name}Joint(world){{ Q:[0.0 0.0 0.1] }}\n{obj.name}({obj.name}Joint) {{ shape:ssBox, Q:"t({x} {y} .0)", size:[{w} {h} .2 .02], logical:{{ movable_go }}, color:[{c_str}], joint:rigid, contact: 1 }}'
    elif obj.obj_type == "goal_location":
            return f'{obj.name} (floor){{ shape:ssBox, Q:"t({x} {y} .1)", size:[{w} {h} .2 .02], color:[{c_str} .3], contact:0, joint:rigid, logical:{{goal}} }}'
    elif obj.obj_type == "agent":
        rad = round(w/2, 3)
        return f'egoJoint(world){{ Q:[{x} {y} 0.1] }}\nego(egoJoint) {{\n    shape:ssCylinder, size:[{rad} {rad} .02], color:[0.96 0.74 0.30], logical:{{agent}}, limits: [-4 4 -4 4],\n    joint:transXY, contact: 1\n}}'
    return ""

def parse_g_file(content):
    pos = 0
    length = len(content)
    header_regex = re.compile(r'([\w\d_]+)\s*\([^\)]+\)\s*\{')
    
    parsed_objects = []
    config_data = {} # To store global config like world size if found

    # Extract Camera or Base if possible
    inc_match = re.search(r'Include:\s*(<[^>]+>)', content)
    if inc_match: config_data['base_file'] = inc_match.group(1)
        
    cam_match = re.search(r'camera_gl\s*\(world\)\s*\{\s*([^}]+)\s*\}', content)
    if cam_match: config_data['camera'] = cam_match.group(1).strip()

    while pos < length:
        match = header_regex.search(content, pos)
        if not match: break
        
        name = match.group(1)
        start_idx = match.end()
        brace_count = 1
        curr = start_idx
        
        while curr < length and brace_count > 0:
            if content[curr] == '{': brace_count += 1
            elif content[curr] == '}': brace_count -= 1
            curr += 1
        
        props = content[start_idx : curr-1]
        pos = curr
        
        # Skip base walls
        if name in ["floor", "wall_north", "wall_south", "wall_east", "wall_west"]:
            continue

        has_shape = "shape" in props or "type" in props
        if not has_shape: continue 
        if "camera" in props or "_vis" in name: continue 
        
        # Extraction Logic
        x, y = 0.0, 0.0
        w, h = 0.1, 0.1
        
        # Q Extraction
        q_match = re.search(r'Q\s*[:=]\s*"?t\(([-\d\.]+)\s+([-\d\.]+)', props)
        if not q_match:
            # Fallback for bracket format
            q_match = re.search(r'Q\s*[:=]\s*\[([-\d\.]+)\s+([-\d\.]+)', props)
        
        if q_match:
            x, y = float(q_match.group(1)), float(q_match.group(2))
            
        # Size Extraction
        s_match = re.search(r'size\s*[:=]\s*\[([-\d\.]+)\s+([-\d\.]+)', props)
        if s_match:
            w, h = float(s_match.group(1)), float(s_match.group(2))

        # Type logic
        otype = "wall"
        color = "brown"
        
        if "agent" in props:
            otype = "agent"
            color = "yellow"
            w = w * 2 
            h = h * 2
        elif "movable_go" in props:
            otype = "goal_object"
            c_match = re.search(r'color\s*[:=]\s*(\[[^\]]+\])', props)
            color = parse_color(c_match.group(1)) if c_match else "blue"
        elif "movable_o" in props:
            otype = "movable"
            c_match = re.search(r'color\s*[:=]\s*(\[[^\]]+\])', props)
            color = parse_color(c_match.group(1)) if c_match else "#ffffff"
        elif "goal" in props and "contact:0" in props:
            otype = "goal_location"
            color = "red"
            c_match = re.search(r'color\s*[:=]\s*(\[[^\]]+\])', props)
            if c_match: color = parse_color(c_match.group(1))
        elif "color" in props:
            otype = "wall"
            color = "brown"
        
        parsed_objects.append({
            'name': name.split('_')[0], 
            'full_name': name,
            'w': w, 'h': h, 
            'x': x, 'y': y, 
            'type': otype, 
            'color': color
        })
        
    return parsed_objects, config_data