import bpy
import random
import math
from mathutils import Vector

# =======================
# Configuration Settings
# =======================
NUM_DRONES = random.randint(3, 7)
NUM_HOSPITALS = random.randint(5, 10)
NUM_CLOUDS = NUM_HOSPITALS * 2

CITY_GRID_SIZE = 20
BUILDING_SPACING = 5.0

MIN_FLOORS = 2
MAX_FLOORS = 12

HOSPITAL_RADIUS = 2
HOSPITAL_HEIGHT = 8

CLOUD_RADIUS = 3
CLOUD_FLATTEN_SCALE_Z = 0.3
CLOUD_ALTITUDE = 10
CLOUD_SPEED = 0.1

DRONE_ALTITUDE = CLOUD_ALTITUDE  # Drones move at the same Z-axis as clouds
DRONE_SIZE = 1.5  # Increased drone size
DRONE_SPEED = 0.15  # Slightly faster for better avoidance
DRONE_AVOIDANCE_RADIUS = CLOUD_RADIUS + 3  # Larger avoidance area

CITY_CENTER = Vector((0, 0, 0))
CITY_BOUNDARY_X = CITY_GRID_SIZE * BUILDING_SPACING / 2
CITY_BOUNDARY_Y = CITY_GRID_SIZE * BUILDING_SPACING / 2

# ================
# Helper Functions
# ================

def clear_scene():
    """Delete all existing objects in the scene."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

def create_rain_cloud(location, direction):
    """Create a rain cloud at the specified location with a random direction."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=CLOUD_RADIUS, location=location)
    cloud = bpy.context.object
    cloud.name = "Rain_Cloud"
    cloud.scale = (1, 1, CLOUD_FLATTEN_SCALE_Z)
    
    # Add cloud material
    mat = bpy.data.materials.new(name="Cloud_Material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    shader = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
    shader.inputs['Roughness'].default_value = 0.9
    output = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    
    cloud.data.materials.append(mat)
    cloud["direction"] = direction
    return cloud

def create_drone(location):
    """Create a detailed drone model at the specified location."""
    # Drone body
    bpy.ops.mesh.primitive_cylinder_add(radius=DRONE_SIZE / 3, depth=0.5, location=location)
    drone_body = bpy.context.object
    drone_body.name = "Drone_Body"

    # Add propellers
    for i in range(4):
        angle = math.radians(90 * i)
        propeller_offset = Vector((math.cos(angle), math.sin(angle), 0)) * DRONE_SIZE * 0.5
        propeller_location = location + propeller_offset
        bpy.ops.mesh.primitive_cylinder_add(radius=DRONE_SIZE / 10, depth=0.2, location=propeller_location)
        propeller = bpy.context.object
        propeller.rotation_euler = (0, 0, angle)
        propeller.name = f"Drone_Propeller_{i}"

    # Add material to drone
    mat = bpy.data.materials.new(name="Drone_Material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    shader = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (0.1, 0.1, 0.1, 1)
    shader.inputs['Metallic'].default_value = 0.8
    shader.inputs['Roughness'].default_value = 0.2
    output = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    
    drone_body.data.materials.append(mat)
    for i in range(4):
        bpy.data.objects[f"Drone_Propeller_{i}"].data.materials.append(mat)

    return drone_body

def create_building(location, width, depth, height):
    """Create a unique building with specified dimensions."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    building = bpy.context.object
    building.scale = (width, depth, height / 2)
    building.location.z = height / 2  # Raise to ground level

    # Assign building material (less colorful)
    mat = bpy.data.materials.new(name="Building_Material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    shader = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (random.uniform(0.3, 0.6), random.uniform(0.3, 0.6), random.uniform(0.3, 0.6), 1)
    shader.inputs['Roughness'].default_value = 0.8
    output = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    
    building.data.materials.append(mat)
    return building

def create_hospital(location):
    """Create a hospital cylinder."""
    bpy.ops.mesh.primitive_cylinder_add(radius=HOSPITAL_RADIUS, depth=HOSPITAL_HEIGHT, location=location)
    hospital = bpy.context.object
    hospital.name = "Hospital"

    # Assign hospital material
    mat = bpy.data.materials.new(name="Hospital_Material")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    shader = nodes.new(type='ShaderNodeBsdfPrincipled')
    shader.inputs['Base Color'].default_value = (1, 0, 0, 1)  # Red color
    shader.inputs['Roughness'].default_value = 0.5
    output = nodes.new(type='ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs['BSDF'], output.inputs['Surface'])
    
    hospital.data.materials.append(mat)
    return hospital

def move_clouds(clouds):
    """Move clouds in a smooth random path, avoiding hospitals."""
    for cloud in clouds:
        direction = Vector(cloud["direction"])
        new_pos = cloud.location + direction * CLOUD_SPEED

        # Check hospital proximity
        near_hospital = any(
            (Vector((h.location.x, h.location.y, CLOUD_ALTITUDE)) - new_pos).length < CLOUD_RADIUS + HOSPITAL_RADIUS
            for h in hospitals
        )

        # Bounce off boundaries or hospitals
        if abs(new_pos.x) > CITY_BOUNDARY_X or near_hospital:
            direction.x *= -1
        if abs(new_pos.y) > CITY_BOUNDARY_Y or near_hospital:
            direction.y *= -1

        cloud.location += direction * CLOUD_SPEED
        cloud["direction"] = direction

def move_drone(drone, target, clouds):
    """Move the drone towards the target, avoiding clouds."""
    current_pos = Vector(drone.location)
    target_vector = target - current_pos
    attraction = target_vector.normalized() if target_vector.length > 0 else Vector()

    repulsion = Vector()
    for cloud in clouds:
        cloud_pos = Vector((cloud.location.x, cloud.location.y, 0))
        drone_pos_2d = Vector((current_pos.x, current_pos.y, 0))
        distance = (cloud_pos - drone_pos_2d).length

        if distance < DRONE_AVOIDANCE_RADIUS:
            direction = (drone_pos_2d - cloud_pos).normalized()
            strength = 1.5 * (DRONE_AVOIDANCE_RADIUS - distance) / DRONE_AVOIDANCE_RADIUS
            repulsion += direction * strength

    movement = attraction + repulsion
    if movement.length > 0:
        movement.normalize()

    new_pos = current_pos + movement * DRONE_SPEED
    new_pos.z = DRONE_ALTITUDE  # Maintain altitude (same as clouds)
    drone.location = new_pos

# =========================
# Main Script Execution
# =========================
clear_scene()

# Create city grid
for x in range(CITY_GRID_SIZE):
    for y in range(CITY_GRID_SIZE):
        width = random.uniform(1, 3)
        depth = random.uniform(1, 3)
        height = random.uniform(MIN_FLOORS, MAX_FLOORS)
        pos_x = (x - CITY_GRID_SIZE/2) * BUILDING_SPACING
        pos_y = (y - CITY_GRID_SIZE/2) * BUILDING_SPACING
        create_building(Vector((pos_x, pos_y, 0)), width, depth, height)

# Create hospitals
hospitals = []
hospital_positions = []
for _ in range(NUM_HOSPITALS):
    while True:
        pos = Vector((
            random.uniform(-CITY_BOUNDARY_X, CITY_BOUNDARY_X),
            random.uniform(-CITY_BOUNDARY_Y, CITY_BOUNDARY_Y),
            HOSPITAL_HEIGHT / 2
        ))
        if all((pos - p).length > HOSPITAL_RADIUS * 2 for p in hospital_positions):
            break
    hospital_positions.append(pos)
    hospitals.append(create_hospital(pos))

# Create clouds
clouds = []
for _ in range(NUM_CLOUDS):
    while True:
        pos = Vector((
            random.uniform(-CITY_BOUNDARY_X, CITY_BOUNDARY_X),
            random.uniform(-CITY_BOUNDARY_Y, CITY_BOUNDARY_Y),
            CLOUD_ALTITUDE
        ))
        if all((pos - p).length > CLOUD_RADIUS * 2 for p in [c.location for c in clouds]) and \
           all((pos - p).length > (CLOUD_RADIUS + HOSPITAL_RADIUS) for p in hospital_positions):
            break
    direction = Vector((random.uniform(-1, 1), random.uniform(-1, 1), 0)).normalized()
    clouds.append(create_rain_cloud(pos, direction))

# Initialize drones
drones = []
for _ in range(NUM_DRONES):
    start_hospital = random.choice(hospitals)
    start = start_hospital.location.copy()
    start.z = DRONE_ALTITUDE  # Set drone altitude to match clouds

    end_hospital = random.choice([h for h in hospitals if h != start_hospital])
    end = end_hospital.location.copy()
    end.z = DRONE_ALTITUDE  # Set target altitude to match clouds

    drone = create_drone(start)
    drones.append((drone, Vector(end), start_hospital))

# Simulation handler
def update_scene(scene):
    move_clouds(clouds)

    for idx, (drone, target, current_hospital) in enumerate(drones):
        # Check if target reached before moving
        if (drone.location - target).length < DRONE_SPEED * 2:
            # Find new target hospital (different from current)
            new_hospital = random.choice([h for h in hospitals if h != current_hospital])
            new_target = new_hospital.location.copy()
            new_target.z = DRONE_ALTITUDE  # Set target altitude to match clouds

            # Move drone to new starting position
            departure_point = current_hospital.location.copy()
            departure_point.z = DRONE_ALTITUDE  # Set departure altitude to match clouds
            drone.location = departure_point

            drones[idx] = (drone, Vector(new_target), new_hospital)
            continue

        # Normal movement
        move_drone(drone, target, clouds)

# Register the simulation update function
bpy.app.handlers.frame_change_pre.append(update_scene)

print("Enhanced simulation setup complete!")
