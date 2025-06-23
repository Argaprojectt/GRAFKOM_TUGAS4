from flask import Flask, request, jsonify, send_from_directory
import math
import os

app = Flask(__name__, static_folder='.', static_url_path='')

# Store objects on the server side. This global variable will persist
# as long as the server is running.
objects_store = []

@app.route('/')
def index():
    """Serves the main HTML file."""
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    """Serves static files like main.js."""
    return send_from_directory('.', path)

@app.route('/get_objects', methods=['GET'])
def get_objects():
    """Returns all objects stored on the server."""
    return jsonify({'success': True, 'objects': objects_store})

@app.route('/transform', methods=['POST'])
def transform():
    """Applies transformations (translate, rotate, scale) to a selected object."""
    data = request.get_json()
    transform_type = data.get('transformType')
    value1 = data.get('value1') # E.g., dx, angle, sx
    value2 = data.get('value2') # E.g., dy, sy
    object_id = data.get('objectId')
    
    # Ensure object_id is valid for the server's current objects_store
    if not (isinstance(object_id, int) and 0 <= object_id < len(objects_store)):
        return jsonify({'success': False, 'error': 'Invalid object ID provided by client.'}), 400

    obj_to_transform = objects_store[object_id]

    try:
        if transform_type == 'translate':
            dx, dy = value1, value2
            if obj_to_transform['type'] == 'point':
                obj_to_transform['x'] += dx
                obj_to_transform['y'] += dy
            elif obj_to_transform['type'] in ('line', 'rectangle', 'ellipse'):
                obj_to_transform['x1'] += dx
                obj_to_transform['y1'] += dy
                obj_to_transform['x2'] += dx
                obj_to_transform['y2'] += dy

        elif transform_type == 'rotate':
            angle_rad = math.radians(value1)
            
            # Determine the center of rotation for the object
            if obj_to_transform['type'] == 'point':
                cx, cy = obj_to_transform['x'], obj_to_transform['y']
            elif obj_to_transform['type'] in ('line', 'rectangle', 'ellipse'):
                cx, cy = (obj_to_transform['x1'] + obj_to_transform['x2']) / 2, (obj_to_transform['y1'] + obj_to_transform['y2']) / 2

            # Apply rotation based on object type
            if obj_to_transform['type'] == 'point':
                px, py = obj_to_transform['x'], obj_to_transform['y']
                # Correct rotation formula for a point around a center (cx, cy)
                rotated_x = cx + (px - cx) * math.cos(angle_rad) - (py - cy) * math.sin(angle_rad)
                rotated_y = cy + (px - cx) * math.sin(angle_rad) + (py - cy) * math.cos(angle_rad)
                obj_to_transform['x'], obj_to_transform['y'] = rotated_x, rotated_y
            elif obj_to_transform['type'] == 'line':
                p1x, p1y = obj_to_transform['x1'], obj_to_transform['y1']
                p2x, p2y = obj_to_transform['x2'], obj_to_transform['y2']
                
                # Correct rotation formula for line endpoints around a center (cx, cy)
                rotated_x1 = cx + (p1x - cx) * math.cos(angle_rad) - (p1y - cy) * math.sin(angle_rad)
                rotated_y1 = cy + (p1x - cx) * math.sin(angle_rad) + (p1y - cy) * math.cos(angle_rad)
                rotated_x2 = cx + (p2x - cx) * math.cos(angle_rad) - (p2y - cy) * math.sin(angle_rad)
                rotated_y2 = cy + (p2x - cx) * math.sin(angle_rad) + (p2y - cy) * math.cos(angle_rad)
                
                obj_to_transform['x1'], obj_to_transform['y1'] = rotated_x1, rotated_y1
                obj_to_transform['x2'], obj_to_transform['y2'] = rotated_x2, rotated_y2
            elif obj_to_transform['type'] == 'rectangle':
                # For rectangles, rotate its corners and then re-calculate the bounding box.
                # This matches the client-side rendering which draws axis-aligned rectangles.
                corners = [
                    (obj_to_transform['x1'], obj_to_transform['y1']),
                    (obj_to_transform['x2'], obj_to_transform['y1']),
                    (obj_to_transform['x2'], obj_to_transform['y2']),
                    (obj_to_transform['x1'], obj_to_transform['y2'])
                ]
                rotated_corners = []
                for p_x, p_y in corners:
                    new_x = cx + (p_x - cx) * math.cos(angle_rad) - (p_y - cy) * math.sin(angle_rad)
                    new_y = cy + (p_x - cx) * math.sin(angle_rad) + (p_y - cy) * math.cos(angle_rad)
                    rotated_corners.append((new_x, new_y))

                all_xs = [p[0] for p in rotated_corners]
                all_ys = [p[1] for p in rotated_corners]
                obj_to_transform['x1'] = min(all_xs)
                obj_to_transform['y1'] = min(all_ys)
                obj_to_transform['x2'] = max(all_xs)
                obj_to_transform['y2'] = max(all_ys)
            elif obj_to_transform['type'] == 'ellipse':
                # For ellipses, just rotate its center and keep dimensions.
                # This is a simplification; full ellipse rotation is more complex.
                px, py = (obj_to_transform['x1'] + obj_to_transform['x2']) / 2, (obj_to_transform['y1'] + obj_to_transform['y2']) / 2
                
                rotated_x = cx + (px - cx) * math.cos(angle_rad) - (py - cy) * math.sin(angle_rad)
                rotated_y = cy + (px - cx) * math.sin(angle_rad) + (py - cy) * math.cos(angle_rad)

                width = obj_to_transform['x2'] - obj_to_transform['x1']
                height = obj_to_transform['y2'] - obj_to_transform['y1']
                obj_to_transform['x1'] = rotated_x - width / 2
                obj_to_transform['y1'] = rotated_y - height / 2
                obj_to_transform['x2'] = rotated_x + width / 2
                obj_to_transform['y2'] = rotated_y + height / 2


        elif transform_type == 'scale':
            sx, sy = value1, value2

            # Determine the scaling center for the object
            if obj_to_transform['type'] == 'point':
                # For points, scaling affects position relative to origin (0,0) by default.
                obj_to_transform['x'] *= sx
                obj_to_transform['y'] *= sy
            elif obj_to_transform['type'] in ('line', 'rectangle', 'ellipse'):
                center_x = (obj_to_transform['x1'] + obj_to_transform['x2']) / 2
                center_y = (obj_to_transform['y1'] + obj_to_transform['y2']) / 2
                
                # Scale the coordinates relative to the object's center
                obj_to_transform['x1'] = center_x + (obj_to_transform['x1'] - center_x) * sx
                obj_to_transform['y1'] = center_y + (obj_to_transform['y1'] - center_y) * sy
                obj_to_transform['x2'] = center_x + (obj_to_transform['x2'] - center_x) * sx
                obj_to_transform['y2'] = center_y + (obj_to_transform['y2'] - center_y) * sy
                
                # For ellipses, ensure radius dimensions also scale correctly
                if obj_to_transform['type'] == 'ellipse':
                    # Recalculate based on new x1,y1,x2,y2 which now represent the new bounding box
                    pass # x1, y1, x2, y2 correctly define the new bounding box for ellipse rendering on client

        # Update the objects_store with the modified object
        objects_store[object_id] = obj_to_transform

        return jsonify({'success': True, 'updatedObject': obj_to_transform, 'objectId': object_id})

    except (ValueError, TypeError) as e:
        # Catch errors related to invalid input types
        print(f"Input type error during transformation: {e}")
        return jsonify({'success': False, 'error': f'Invalid input for transformation: {e}'}), 400
    except Exception as e:
        # Catch any other unexpected errors during transformation
        print(f"An unexpected error occurred during transformation: {e}")
        return jsonify({'success': False, 'error': f'An unexpected error occurred: {e}'}), 500

@app.route('/clip', methods=['POST'])
def clip():
    """Applies clipping to objects based on a given windowing rectangle."""
    data = request.get_json()
    window_rect = data.get('windowRect')
    client_objects = data.get('objects', [])

    if not window_rect or not all(k in window_rect for k in ['x1', 'y1', 'x2', 'y2']):
        return jsonify({'success': False, 'error': 'Invalid windowing rectangle data.'}), 400

    clipped_objects = []

    # Constants for Cohen-Sutherland clipping
    INSIDE = 0  # 0000
    LEFT = 1    # 0001
    RIGHT = 2   # 0010
    BOTTOM = 4  # 0100
    TOP = 8     # 1000

    def compute_outcode(x, y, xmin, ymin, xmax, ymax):
        """Computes the region code for a point (x, y)."""
        code = INSIDE
        if x < xmin:      code |= LEFT
        elif x > xmax:    code |= RIGHT
        if y < ymin:      code |= BOTTOM
        elif y > ymax:    code |= TOP
        return code

    def cohen_sutherland_clip(x1, y1, x2, y2, xmin, ymin, xmax, ymax):
        """
        Cohen-Sutherland line clipping algorithm.
        Returns (x1, y1, x2, y2) for the clipped line or None if entirely outside.
        """
        outcode1 = compute_outcode(x1, y1, xmin, ymin, xmax, ymax)
        outcode2 = compute_outcode(x2, y2, xmin, ymin, xmax, ymax)
        accept = False

        while True:
            if (outcode1 == 0) and (outcode2 == 0): # Both endpoints inside
                accept = True
                break
            elif (outcode1 & outcode2) != 0: # Both endpoints outside and on same side
                break
            else: # Line crosses one of the boundaries
                x, y = 0, 0
                outcode_out = outcode1 if outcode1 != 0 else outcode2

                # Find intersection point
                if outcode_out & TOP:
                    # Line intersects top boundary
                    if (y2 - y1) != 0: # Avoid division by zero for vertical lines
                        x = x1 + (x2 - x1) * (ymax - y1) / (y2 - y1)
                    else:
                        x = x1 # If line is horizontal and at ymax, x remains the same
                    y = ymax
                elif outcode_out & BOTTOM:
                    # Line intersects bottom boundary
                    if (y2 - y1) != 0: # Avoid division by zero for vertical lines
                        x = x1 + (x2 - x1) * (ymin - y1) / (y2 - y1)
                    else:
                        x = x1
                    y = ymin
                elif outcode_out & RIGHT:
                    # Line intersects right boundary
                    if (x2 - x1) != 0: # Avoid division by zero for horizontal lines
                        y = y1 + (y2 - y1) * (xmax - x1) / (x2 - x1)
                    else:
                        y = y1
                    x = xmax
                elif outcode_out & LEFT:
                    # Line intersects left boundary
                    if (x2 - x1) != 0: # Avoid division by zero for horizontal lines
                        y = y1 + (y2 - y1) * (xmin - x1) / (x2 - x1)
                    else:
                        y = y1
                    x = xmin

                # Move point to intersection and recompute outcode
                if outcode_out == outcode1:
                    x1, y1 = x, y
                    outcode1 = compute_outcode(x1, y1, xmin, ymin, xmax, ymax)
                else:
                    x2, y2 = x, y
                    outcode2 = compute_outcode(x2, y2, xmin, ymin, xmax, ymax)
        
        if accept:
            return (x1, y1, x2, y2)
        else:
            return None

    for obj in client_objects:
        if obj['type'] == 'point':
            # Check if point is within the normalized window rectangle
            if (window_rect['x1'] <= obj['x'] <= window_rect['x2'] and
                window_rect['y1'] <= obj['y'] <= window_rect['y2']):
                clipped_objects.append(obj)
        elif obj['type'] == 'line':
            clipped_line_coords = cohen_sutherland_clip(obj['x1'], obj['y1'], obj['x2'], obj['y2'],
                                                         window_rect['x1'], window_rect['y1'], window_rect['x2'], window_rect['y2'])
            if clipped_line_coords:
                clipped_objects.append({
                    'type': 'line',
                    'x1': clipped_line_coords[0], 'y1': clipped_line_coords[1],
                    'x2': clipped_line_coords[2], 'y2': clipped_line_coords[3],
                    'color': obj['color'], 'thickness': obj['thickness']
                })
        elif obj['type'] == 'rectangle':
            # Clip rectangle by finding the intersection of its bounding box with the window
            obj_min_x, obj_max_x = min(obj['x1'], obj['x2']), max(obj['x1'], obj['x2'])
            obj_min_y, obj_max_y = min(obj['y1'], obj['y2']), max(obj['y1'], obj['y2'])

            new_x1 = max(obj_min_x, window_rect['x1'])
            new_y1 = max(obj_min_y, window_rect['y1'])
            new_x2 = min(obj_max_x, window_rect['x2'])
            new_y2 = min(obj_max_y, window_rect['y2'])

            if new_x2 > new_x1 and new_y2 > new_y1: # Ensure the clipped rectangle is still valid (not just a line/point)
                clipped_objects.append({
                    'type': 'rectangle',
                    'x1': new_x1, 'y1': new_y1,
                    'x2': new_x2, 'y2': new_y2,
                    'color': obj['color'], 'thickness': obj['thickness']
                })
        elif obj['type'] == 'ellipse':
            # For ellipses, we simplify by only including them if their entire bounding box
            # is within the clipping window. Partial ellipse clipping is much more complex.
            obj_min_x, obj_max_x = min(obj['x1'], obj['x2']), max(obj['x1'], obj['x2'])
            obj_min_y, obj_max_y = min(obj['y1'], obj['y2']), max(obj['y1'], obj['y2'])

            if (obj_min_x >= window_rect['x1'] and obj_max_x <= window_rect['x2'] and
                obj_min_y >= window_rect['y1'] and obj_max_y <= window_rect['y2']):
                clipped_objects.append(obj)
            # Else, if it's partially outside, it's discarded in this simplified approach.
        
    global objects_store
    objects_store = clipped_objects # Update the server's store with the clipped objects

    return jsonify({'success': True, 'clippedObjects': clipped_objects})

@app.route('/clear_objects', methods=['POST'])
def clear_objects():
    """Clears all objects from the server storage."""
    global objects_store
    objects_store = []
    return jsonify({'success': True})

# This is a development server. In production, use a production WSGI server.
if __name__ == '__main__':
    # Initialize objects_store for a fresh start each time main.py is run
    objects_store = [] 
    app.run(debug=True) # debug=True enables auto-reloading and better error messages
