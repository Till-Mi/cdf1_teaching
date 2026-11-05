"""
Geometry basics -- reusable Rhino.Geometry functions for Grasshopper.

Adding a new function with Copilot
-----------------------------------
1. Open this file and select this chat model, then ask Copilot something like:
   "Add a function here, all in Rhino geometry, that builds a <your shape/idea>.
   Follow the same style as create_cone / create_fractal_tree (defaults for
   optional inputs, a docstring listing params, return a Rhino.Geometry object)."
2. Once the function is added, ask Copilot:
   "Give me the Python code to use this function in a Grasshopper GHPython 3
   component, importing it from computational_design_and_fabrication."
3. Copy the snippet Copilot gives you into a GHPython component, wire up the
   inputs as sliders/panels, and set the output variable (e.g. `a`).
"""

import math
import Rhino.Geometry as rg

def create_cone(base_point=None, height=10.0, radius=5.0, cap_bottom=True):
    """
    Build a cone as a Brep.

    base_point : Rhino.Geometry.Point3d -- center of the cone's base circle
    height     : float -- cone height along the base plane's normal (Z by default)
    radius     : float -- base circle radius
    cap_bottom : bool  -- whether to cap the base circle (closed vs open cone)

    Returns a Rhino.Geometry.Brep.
    """
    if base_point is None:
        base_point = rg.Point3d(0, 0, 0)

    plane = rg.Plane(base_point, rg.Vector3d.ZAxis)
    cone = rg.Cone(plane, height, radius)
    return cone.ToBrep(cap_bottom)


def create_pyramid(base_point=None, height=10.0, base_width=10.0, cap_bottom=True):
    """
    Build a square-based pyramid as a Brep.

    base_point : Rhino.Geometry.Point3d -- center of the pyramid's base
    height     : float -- pyramid height along the base plane's normal (Z by default)
    base_width : float -- side length of the square base
    cap_bottom : bool  -- whether to cap the base (closed vs open pyramid)

    Returns a Rhino.Geometry.Brep.
    """
    if base_point is None:
        base_point = rg.Point3d(0, 0, 0)

    plane = rg.Plane(base_point, rg.Vector3d.ZAxis)
    half_width = base_width / 2.0
    corners = [
        plane.PointAt(-half_width, -half_width),
        plane.PointAt(half_width, -half_width),
        plane.PointAt(half_width, half_width),
        plane.PointAt(-half_width, half_width),
    ]
    apex = base_point + plane.ZAxis * height

    tolerance = 0.001
    faces = []
    if cap_bottom:
        base = rg.Brep.CreateFromCornerPoints(
            corners[0], corners[3], corners[2], corners[1], tolerance
        )
        if base is None:
            raise RuntimeError("Could not create the pyramid base.")
        faces.append(base)

    for i in range(4):
        face = rg.Brep.CreateFromCornerPoints(
            corners[i], corners[(i + 1) % 4], apex, tolerance
        )
        if face is None:
            raise RuntimeError("Could not create a pyramid side.")
        faces.append(face)

    pyramid = rg.Brep.JoinBreps(faces, tolerance)
    if pyramid is None or len(pyramid) != 1:
        raise RuntimeError("Could not join the pyramid faces into one Brep.")
    return pyramid[0]


def create_box(origin=None, length=10.0, width=10.0, height=10.0):
    """
    Build a box as a Brep from an origin point or plane and three dimensions.

    origin : Rhino.Geometry.Point3d or Rhino.Geometry.Plane -- lower corner (world XY if a point)
    length : float -- size along the origin plane's X-axis
    width : float -- size along the origin plane's Y-axis
    height : float -- size along the origin plane's Z-axis

    Returns a Rhino.Geometry.Brep.
    """
    if origin is None:
        origin = rg.Point3d(0, 0, 0)

    if isinstance(origin, rg.Plane):
        plane = origin
    elif isinstance(origin, rg.Point3d):
        plane = rg.Plane(origin, rg.Vector3d.ZAxis)
    else:
        raise TypeError("origin must be a Rhino.Geometry.Point3d or Rhino.Geometry.Plane.")

    box = rg.Box(
        plane,
        rg.Interval(0, length),
        rg.Interval(0, width),
        rg.Interval(0, height),
    )
    return box.ToBrep()


def create_staircase_boxes(
    box_count=5,
    origin=None,
    length=10.0,
    width=10.0,
    height=10.0,
    step_y=None,
    step_z=None,
):
    """
    Create boxes stepping along the world Y and Z axes.

    box_count : int -- number of boxes
    origin    : Rhino.Geometry.Point3d or Rhino.Geometry.Plane -- first box origin
    length    : float -- box size along X
    width     : float -- box size along Y
    height    : float -- box size along Z
    step_y    : float -- Y offset between boxes (box width by default)
    step_z    : float -- Z offset between boxes (box height by default)

    Returns a list of Rhino.Geometry.Brep boxes.
    """
    if isinstance(box_count, bool) or int(box_count) != box_count or box_count < 1:
        raise ValueError("box_count must be a positive integer.")
    if length <= 0 or width <= 0 or height <= 0:
        raise ValueError("length, width, and height must be positive.")
    if step_y is None:
        step_y = width
    if step_z is None:
        step_z = height
    if step_y <= 0 or step_z <= 0:
        raise ValueError("step_y and step_z must be positive.")

    first_box = create_box(origin, length, width, height)
    boxes = []
    for index in range(int(box_count)):
        box = first_box.DuplicateBrep()
        transform = rg.Transform.Translation(
            rg.Vector3d(0, step_y * index, step_z * index)
        )
        if not box.Transform(transform):
            raise RuntimeError("Could not move a staircase box.")
        boxes.append(box)
    return boxes


def create_window_opening(
    box,
    width=2.0,
    height=2.0,
    depth=1.0,
    center_point=None,
    face="+Y",
    tolerance=0.001,
):
    """
    Cut a rectangular recessed window opening into one vertical face of an axis-aligned Brep.

    box          : Rhino.Geometry.Brep -- the box to cut
    width        : float -- opening width along the selected face
    height       : float -- opening height along the world Z-axis
    depth        : float -- distance the opening extends into the box
    center_point : Rhino.Geometry.Point3d -- opening center in the face plane (box center by default)
    face         : str -- selected face: "+X", "-X", "+Y", or "-Y"
    tolerance    : float -- boolean and cutter tolerance

    Returns a list of Rhino.Geometry.Brep results, like boolean_difference.
    """
    if not isinstance(box, rg.Brep):
        raise TypeError("box must be a Rhino.Geometry.Brep.")
    if width <= 0 or height <= 0 or depth <= 0 or tolerance <= 0:
        raise ValueError("width, height, depth, and tolerance must be positive.")
    if not isinstance(face, str):
        raise TypeError('face must be "+X", "-X", "+Y", or "-Y".')

    face = face.upper()
    if face not in ("+X", "-X", "+Y", "-Y"):
        raise ValueError('face must be "+X", "-X", "+Y", or "-Y".')

    bounds = box.GetBoundingBox(True)
    if not bounds.IsValid:
        raise ValueError("box must have a valid bounding box.")

    if center_point is None:
        center_point = bounds.Center
    elif not isinstance(center_point, rg.Point3d):
        raise TypeError("center_point must be a Rhino.Geometry.Point3d.")

    if face.endswith("X"):
        axis_size = bounds.Max.X - bounds.Min.X
        face_coordinate = bounds.Max.X if face.startswith("+") else bounds.Min.X
        center = rg.Point3d(face_coordinate, center_point.Y, center_point.Z)
        if (
            center.Y - width / 2.0 < bounds.Min.Y
            or center.Y + width / 2.0 > bounds.Max.Y
            or center.Z - height / 2.0 < bounds.Min.Z
            or center.Z + height / 2.0 > bounds.Max.Z
        ):
            raise ValueError("The opening must fit within the selected face.")

        x_interval = (
            rg.Interval(face_coordinate - depth, face_coordinate + tolerance)
            if face.startswith("+")
            else rg.Interval(face_coordinate - tolerance, face_coordinate + depth)
        )
        y_interval = rg.Interval(center.Y - width / 2.0, center.Y + width / 2.0)
    else:
        axis_size = bounds.Max.Y - bounds.Min.Y
        face_coordinate = bounds.Max.Y if face.startswith("+") else bounds.Min.Y
        center = rg.Point3d(center_point.X, face_coordinate, center_point.Z)
        if (
            center.X - width / 2.0 < bounds.Min.X
            or center.X + width / 2.0 > bounds.Max.X
            or center.Z - height / 2.0 < bounds.Min.Z
            or center.Z + height / 2.0 > bounds.Max.Z
        ):
            raise ValueError("The opening must fit within the selected face.")

        x_interval = rg.Interval(center.X - width / 2.0, center.X + width / 2.0)
        y_interval = (
            rg.Interval(face_coordinate - depth, face_coordinate + tolerance)
            if face.startswith("+")
            else rg.Interval(face_coordinate - tolerance, face_coordinate + depth)
        )

    if depth + tolerance >= axis_size:
        raise ValueError("depth must leave material behind the opening.")

    z_interval = rg.Interval(center.Z - height / 2.0, center.Z + height / 2.0)
    cutter = rg.Box(
        rg.Plane(rg.Point3d(0, 0, 0), rg.Vector3d.ZAxis),
        x_interval,
        y_interval,
        z_interval,
    ).ToBrep()
    result = boolean_difference(box, cutter)
    if not result:
        raise RuntimeError("Could not create the window opening.")
    return result


def create_sphere(center_point=None, radius=5.0):
    """
    Build a sphere as a Brep.

    center_point : Rhino.Geometry.Point3d -- center of the sphere (origin by default)
    radius       : float -- sphere radius

    Returns a Rhino.Geometry.Brep.
    """
    if center_point is None:
        center_point = rg.Point3d(10, 0, 2
                                  )

        sphere = rg.Sphere(center_point, radius)
    return rg.Sphere(center_point, radius).ToBrep()

def boolean_difference(brep_a, brep_b):
    """
    Perform a boolean difference operation between two Breps.

    brep_a : Rhino.Geometry.Brep -- the first Brep
    brep_b : Rhino.Geometry.Brep -- the second Brep to subtract from the first

    Returns a list of Rhino.Geometry.Brep resulting from the difference.
    """
    if brep_a is None or brep_b is None:
        raise ValueError("Both brep_a and brep_b must be provided.")

    result = rg.Brep.CreateBooleanDifference(brep_a, brep_b, 0.001)
    return result


def copy_brep_along_z(brep, distance, copy_count):
    """
    Create copies of a Brep, each offset in the +Z direction.

    brep : Rhino.Geometry.Brep -- the Brep to copy
    distance : float -- the Z spacing between consecutive copies
    copy_count : int -- the number of copies to create

    Returns a list of Rhino.Geometry.Brep copies; copy i is moved by distance * (i + 1).
    """
    if brep is None:
        raise ValueError("brep must be provided.")
    if copy_count < 0:
        raise ValueError("copy_count must not be negative.")

    copies = []
    for i in range(1, int(copy_count) + 1):
        copy = brep.DuplicateBrep()
        copy.Transform(rg.Transform.Translation(rg.Vector3d(0, 0, distance * i)))
        copies.append(copy)
    return copies