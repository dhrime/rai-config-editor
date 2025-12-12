import re
from .constants import DEFAULT_BASE_FILE


def rgb_to_str(hex_color):
    if hex_color.startswith("#"):
        r = int(hex_color[1:3], 16) / 255.0
        g = int(hex_color[3:5], 16) / 255.0
        b = int(hex_color[5:7], 16) / 255.0
        return f"{round(r, 4)} {round(g, 4)} {round(b, 4)}"
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
    except:
        return "gray"


def extract_floats(text_block, key):
    # Matches key:[ ... ] or key:"t(...)" robustly across lines
    match = re.search(key + r'\s*[:=]\s*\[(.*?)\]', text_block, re.DOTALL)
    if match:
        inner = match.group(1)
        nums = re.findall(r'-?\d*\.?\d+', inner)
        return [float(n) for n in nums]

    if key == "Q":
        match = re.search(r'Q\s*[:=]\s*"?t\((.*?)\)', text_block, re.DOTALL)
        if match:
            nums = re.findall(r'-?\d*\.?\d+', match.group(1))
            return [float(n) for n in nums]

    return []


def generate_g_string(objects, base_file=DEFAULT_BASE_FILE):
    output = f"Include: {base_file}\n\n"

    for obj in objects:
        x, y = round(obj.x, 3), round(obj.y, 3)
        w, h = round(obj.width, 3), round(obj.height, 3)
        c_str = rgb_to_str(obj.color)

        if obj.obj_type == "wall":
            output += f'{obj.name} (world){{ shape:ssBox, Q:"t({x} {y} 0.3)", size:[{w} {h} 0.6 .02], color:[0.69 0.51 0.45], contact: 1 }}\n'
        elif obj.obj_type == "movable":
            output += f'{obj.name}Joint(world){{ Q:[0.0 0.0 0.1] }}\n{obj.name}({obj.name}Joint) {{ shape:ssBox, Q:"t({x} {y} .0)", size:[{w} {h} .2 .02], logical:{{ movable_o }}, color:[{c_str}], joint:rigid, contact: 1 }}\n'
        elif obj.obj_type == "goal_object":
            output += f'{obj.name}Joint(world){{ Q:[0.0 0.0 0.1] }}\n{obj.name}({obj.name}Joint) {{ shape:ssBox, Q:"t({x} {y} .0)", size:[{w} {h} .2 .02], logical:{{ movable_go }}, color:[{c_str}], joint:rigid, contact: 1 }}\n'
        elif obj.obj_type == "goal_location":
            output += f'{obj.name} (floor){{ shape:ssBox, Q:"t({x} {y} .1)", size:[{w} {h} .2 .02], color:[{c_str} .3], contact:0, joint:rigid, logical:{{goal}} }}\n'
        elif obj.obj_type == "agent":
            rad = round(w / 2, 3)
            # FIX: Write position to the BODY (ego), not the JOINT (egoJoint)
            # egoJoint stays at origin. ego moves relative to it.
            output += f'egoJoint(world){{ Q:[0 0 0.1] }}\nego(egoJoint) {{\n    shape:ssCylinder, Q:[{x} {y} 0], size:[{rad} {rad} .02], color:[0.96 0.74 0.30], logical:{{agent}}, limits: [-4 4 -4 4],\n    joint:transXY, contact: 1\n}}\n'

        output += "\n"

    return output


def parse_g_file(content):
    pos = 0
    length = len(content)
    header_regex = re.compile(r'([\w\d_]+)\s*\([^\)]+\)\s*\{')

    parsed_objects = []

    inc_match = re.search(r'Include:\s*(<[^>]+>)', content)
    base_file = inc_match.group(1) if inc_match else DEFAULT_BASE_FILE

    while pos < length:
        match = header_regex.search(content, pos)
        if not match: break

        name = match.group(1)
        start_idx = match.end()
        brace_count = 1
        curr = start_idx

        while curr < length and brace_count > 0:
            if content[curr] == '{':
                brace_count += 1
            elif content[curr] == '}':
                brace_count -= 1
            curr += 1

        props = content[start_idx: curr - 1]
        pos = curr

        if name in ["floor", "wall_north", "wall_south", "wall_east", "wall_west"]:
            continue

        has_shape = "shape" in props or "type" in props
        if not has_shape: continue
        if "camera" in props or "_vis" in name: continue

        x, y = 0.0, 0.0
        w, h = 0.1, 0.1

        q_nums = extract_floats(props, "Q")
        if len(q_nums) >= 2:
            x, y = q_nums[0], q_nums[1]

        s_nums = extract_floats(props, "size")
        if len(s_nums) >= 2:
            w, h = s_nums[0], s_nums[1]

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
            'name': name.split('_')[0], 'full_name': name,
            'w': w, 'h': h, 'x': x, 'y': y,
            'type': otype, 'color': color
        })

    return parsed_objects, base_file