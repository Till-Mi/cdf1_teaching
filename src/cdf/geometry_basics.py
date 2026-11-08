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
from System.Drawing import Color



def create_cylinder(
    base_point=None, height=10.0, radius=5.0, cap_bottom=True, cap_top=True
):
    """
    Build a cylinder as a Brep.

    base_point : Rhino.Geometry.Point3d -- center of the cylinder's base circle
    height     : float -- cylinder height along the base plane's normal (Z by default)
    radius     : float -- cylinder radius
    cap_bottom : bool  -- whether to cap the base circle
    cap_top    : bool  -- whether to cap the top circle

    Returns a Rhino.Geometry.Brep.
    """
    if base_point is None:
        base_point = rg.Point3d(0, 0, 0)

    plane = rg.Plane(base_point, rg.Vector3d.ZAxis)
    cylinder = rg.Cylinder(rg.Circle(plane, radius), height)
    return cylinder.ToBrep(cap_bottom, cap_top)


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
    length=300.0,
    width=None,
    height=None,
    step_y=None,
    step_z=None,
):
    """
    Create a staircase in complete groups of three steps, with a seating
    platform beside each group. A box_count not divisible by three is rounded
    down to the previous multiple of three.

    The tread depth (a) and riser height (b) follow a + 2b = 63. If only one
    is provided, the other is calculated. Each step and seating platform is a
    solid support rising from the common base (Z=0 for the default origin).
    Seating platforms span three tread depths beside the staircase.

    box_count : int -- requested number of stair steps; rounded down to a multiple of three
    origin    : Rhino.Geometry.Point3d or Rhino.Geometry.Plane -- first step origin
    length    : float -- total width along X: one quarter for the stairs and
                         three quarters for the seating platforms
    width     : float -- tread depth a
    height    : float -- riser height b
    step_y    : float -- alias for tread depth a
    step_z    : float -- alias for riser height b

    Returns a list of Rhino.Geometry.Brep boxes: stair steps followed by
    seating platforms.
    """
    if isinstance(box_count, bool) or int(box_count) != box_count or box_count < 3:
        raise ValueError("box_count must be an integer of at least 3.")
    box_count = int(box_count) // 3 * 3

    if width is not None and step_y is not None and not math.isclose(
        width, step_y, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("width and step_y must match.")
    if height is not None and step_z is not None and not math.isclose(
        height, step_z, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("height and step_z must match.")

    tread_depth = width if width is not None else step_y
    riser_height = height if height is not None else step_z
    if tread_depth is None and riser_height is None:
        tread_depth, riser_height = 28.0, 17.5
    elif tread_depth is None:
        tread_depth = 63.0 - 2.0 * riser_height
    elif riser_height is None:
        riser_height = (63.0 - tread_depth) / 2.0

    if length <= 0 or tread_depth <= 0 or riser_height <= 0:
        raise ValueError("length, tread depth, and riser height must be positive.")
    if not math.isclose(
        tread_depth + 2.0 * riser_height, 63.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("The tread depth and riser height must satisfy a + 2b = 63.")

    stair_width = length / 4.0
    seat_width = 3.0 * length / 4.0
    boxes = []
    for index in range(int(box_count)):
        box = create_box(
            origin, stair_width, tread_depth, riser_height * (index + 1)
        )
        transform = rg.Transform.Translation(
            rg.Vector3d(0, tread_depth * index, 0)
        )
        if not box.Transform(transform):
            raise RuntimeError("Could not move a stair step.")
        boxes.append(box)

    seat_count = int(box_count) // 3
    for index in range(seat_count):
        seat = create_box(
            origin,
            seat_width,
            3.0 * tread_depth,
            3.0 * riser_height * (index + 1),
        )
        transform = rg.Transform.Translation(
            rg.Vector3d(stair_width, 3.0 * tread_depth * index, 0)
        )
        if not seat.Transform(transform):
            raise RuntimeError("Could not move a seating platform.")
        boxes.append(seat)

    return boxes


def create_staircase_pipes(
    box_count=5,
    origin=None,
    length=300.0,
    width=None,
    height=None,
    step_y=None,
    step_z=None,
    pipe_diameter=5.0,
):
    """
    Create hollow vertical pipes along the side of the staircase.

    The pipe count is based on the full staircase depth, not the number of
    steps. box_count is rounded down to a multiple of three to match the
    staircase. The requested diameter is a maximum; pipe diameters are adjusted
    slightly so the row exactly spans the stair depth without gaps or overlap.
    Each pipe rises from the base to 100 cm above the step at its Y position.
    The wall thickness is fixed at 0.5 model units.

    box_count     : int -- number of stair steps
    origin        : Rhino.Geometry.Point3d or Rhino.Geometry.Plane -- stair origin
    length        : float -- total width along X; stairs use one quarter
    width         : float -- tread depth a
    height        : float -- riser height b
    step_y        : float -- alias for tread depth a
    step_z        : float -- alias for riser height b
    pipe_diameter : float -- maximum pipe diameter in model units

    Returns a list of vertical Rhino.Geometry.Brep pipes.
    """
    if isinstance(box_count, bool) or int(box_count) != box_count or box_count < 3:
        raise ValueError("box_count must be an integer of at least 3.")
    box_count = int(box_count) // 3 * 3
    if length <= 0 or pipe_diameter <= 0:
        raise ValueError("length and pipe_diameter must be positive.")
    if width is not None and step_y is not None and not math.isclose(
        width, step_y, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("width and step_y must match.")
    if height is not None and step_z is not None and not math.isclose(
        height, step_z, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("height and step_z must match.")

    tread_depth = width if width is not None else step_y
    riser_height = height if height is not None else step_z
    if tread_depth is None and riser_height is None:
        tread_depth, riser_height = 28.0, 17.5
    elif tread_depth is None:
        tread_depth = 63.0 - 2.0 * riser_height
    elif riser_height is None:
        riser_height = (63.0 - tread_depth) / 2.0
    if tread_depth <= 0 or riser_height <= 0:
        raise ValueError("tread depth and riser height must be positive.")
    if not math.isclose(
        tread_depth + 2.0 * riser_height, 63.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("The tread depth and riser height must satisfy a + 2b = 63.")

    if origin is None:
        base_point = rg.Point3d(0, 0, 0)
    elif isinstance(origin, rg.Point3d):
        base_point = origin
    elif isinstance(origin, rg.Plane):
        base_point = origin.Origin
    else:
        raise TypeError("origin must be a Rhino.Geometry.Point3d or Rhino.Geometry.Plane.")

    total_depth = int(box_count) * tread_depth
    pipe_count = max(1, int(math.ceil(total_depth / pipe_diameter)))
    actual_diameter = total_depth / pipe_count
    wall_thickness = 0.5
    inner_radius = actual_diameter / 2.0 - wall_thickness
    if inner_radius <= 0:
        raise ValueError("wall_thickness must be smaller than the pipe radius.")
    pipes = []

    for index in range(pipe_count):
        y = actual_diameter * (index + 0.5)
        step_index = min(int(y / tread_depth), int(box_count) - 1)
        pipe_base = base_point + rg.Vector3d(
            -actual_diameter / 2.0,
            y,
            0,
        )
        pipe_plane = rg.Plane(pipe_base, rg.Vector3d.ZAxis)
        pipe = rg.Cylinder(
            rg.Circle(pipe_plane, actual_diameter / 2.0),
            riser_height * (step_index + 1) + 100.0,
        ).ToBrep(True, True)
        if pipe is None:
            raise RuntimeError("Could not create a staircase pipe.")

        pipe_height = riser_height * (step_index + 1) + 100.0
        cutter_base = pipe_base + rg.Vector3d(0, 0, -0.01)
        cutter_plane = rg.Plane(cutter_base, rg.Vector3d.ZAxis)
        cutter = rg.Cylinder(
            rg.Circle(cutter_plane, inner_radius),
            pipe_height + 0.02,
        ).ToBrep(True, True)
        if cutter is None:
            raise RuntimeError("Could not create the inner pipe cutter.")
        hollow_pipe = rg.Brep.CreateBooleanDifference(pipe, cutter, 0.001)
        if hollow_pipe is None or len(hollow_pipe) != 1:
            raise RuntimeError("Could not hollow a staircase pipe.")
        pipe = hollow_pipe[0]

        pipes.append(pipe)

    return pipes


def create_staircase_cones(
    box_count=5,
    origin=None,
    length=300.0,
    width=None,
    height=None,
    step_y=None,
    step_z=None,
    cone_diameter=5.0,
):
    """
    Create vertical cones along the right side of the seating staircase.

    box_count is rounded down to a multiple of three to match the staircase.
    The cone count is based on the full staircase depth, not the number of
    steps. Their bases are sized to fill the depth without gaps or overlap.
    Each cone rises from the base to 100 cm above the corresponding stair step.

    box_count    : int -- number of stair steps
    origin       : Rhino.Geometry.Point3d or Rhino.Geometry.Plane -- stair origin
    length       : float -- total width along X
    width        : float -- tread depth a
    height       : float -- riser height b
    step_y       : float -- alias for tread depth a
    step_z       : float -- alias for riser height b
    cone_diameter: float -- maximum cone base diameter in model units

    Returns a list of capped vertical Rhino.Geometry.Brep cones.
    """
    if isinstance(box_count, bool) or int(box_count) != box_count or box_count < 3:
        raise ValueError("box_count must be an integer of at least 3.")
    box_count = int(box_count) // 3 * 3
    if length <= 0 or cone_diameter <= 0:
        raise ValueError("length and cone_diameter must be positive.")
    if width is not None and step_y is not None and not math.isclose(
        width, step_y, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("width and step_y must match.")
    if height is not None and step_z is not None and not math.isclose(
        height, step_z, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("height and step_z must match.")

    tread_depth = width if width is not None else step_y
    riser_height = height if height is not None else step_z
    if tread_depth is None and riser_height is None:
        tread_depth, riser_height = 28.0, 17.5
    elif tread_depth is None:
        tread_depth = 63.0 - 2.0 * riser_height
    elif riser_height is None:
        riser_height = (63.0 - tread_depth) / 2.0
    if tread_depth <= 0 or riser_height <= 0:
        raise ValueError("tread depth and riser height must be positive.")
    if not math.isclose(
        tread_depth + 2.0 * riser_height, 63.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("The tread depth and riser height must satisfy a + 2b = 63.")

    if origin is None:
        base_point = rg.Point3d(0, 0, 0)
    elif isinstance(origin, rg.Point3d):
        base_point = origin
    elif isinstance(origin, rg.Plane):
        base_point = origin.Origin
    else:
        raise TypeError("origin must be a Rhino.Geometry.Point3d or Rhino.Geometry.Plane.")

    total_depth = int(box_count) * tread_depth
    cone_count = max(1, int(math.ceil(total_depth / cone_diameter)))
    actual_diameter = total_depth / cone_count
    radius = actual_diameter / 2.0
    cones = []

    for index in range(cone_count):
        y = actual_diameter * (index + 0.5)
        step_index = min(int(y / tread_depth), int(box_count) - 1)
        cone_base = base_point + rg.Vector3d(length + radius, y, 0)
        cone_plane = rg.Plane(cone_base, rg.Vector3d.ZAxis)
        cone = rg.Cone(
            cone_plane,
            riser_height * (step_index + 1) + 100.0,
            radius,
        ).ToBrep(True)
        if cone is None:
            raise RuntimeError("Could not create a staircase cone.")
        bounds = cone.GetBoundingBox(True)
        if not bounds.IsValid:
            raise RuntimeError("Could not determine the staircase cone bounds.")
        rotation = rg.Transform.Rotation(
            math.pi, rg.Vector3d.XAxis, bounds.Center
        )
        if not cone.Transform(rotation):
            raise RuntimeError("Could not turn a staircase cone upside down.")
        cones.append(cone)

    return cones


def create_staircase_bars(
    box_count=5,
    bar_count=None,
    origin=None,
    length=300.0,
    width=None,
    height=None,
    step_y=None,
    step_z=None,
):
    """
    Create vertical box bars across the back of the full staircase width.

    Bars are 5 cm deep, with a fixed 10 cm clear gap between them. If
    bar_count is specified, their width is adjusted to fit the total width;
    otherwise, 5 cm wide bars are fitted to the total width. Each bar extends
    from the base to 100 cm above the highest seating platform.

    box_count : int -- number of stair steps; must include at least one group of three
    bar_count : int -- number of bars; calculated from seating width if omitted
    origin    : Rhino.Geometry.Point3d or Rhino.Geometry.Plane -- stair origin
    length    : float -- total width along X
    width     : float -- tread depth a
    height    : float -- riser height b
    step_y    : float -- alias for tread depth a
    step_z    : float -- alias for riser height b

    Returns a list of vertical Rhino.Geometry.Brep bars.
    """
    if isinstance(box_count, bool) or int(box_count) != box_count or box_count < 3:
        raise ValueError("box_count must be an integer of at least 3.")
    if bar_count is not None and (
        isinstance(bar_count, bool)
        or int(bar_count) != bar_count
        or bar_count < 1
    ):
        raise ValueError("bar_count must be a positive integer.")
    if length <= 0:
        raise ValueError("length must be positive.")
    if width is not None and step_y is not None and not math.isclose(
        width, step_y, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("width and step_y must match.")
    if height is not None and step_z is not None and not math.isclose(
        height, step_z, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("height and step_z must match.")

    tread_depth = width if width is not None else step_y
    riser_height = height if height is not None else step_z
    if tread_depth is None and riser_height is None:
        tread_depth, riser_height = 28.0, 17.5
    elif tread_depth is None:
        tread_depth = 63.0 - 2.0 * riser_height
    elif riser_height is None:
        riser_height = (63.0 - tread_depth) / 2.0
    if tread_depth <= 0 or riser_height <= 0:
        raise ValueError("tread depth and riser height must be positive.")
    if not math.isclose(
        tread_depth + 2.0 * riser_height, 63.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("The tread depth and riser height must satisfy a + 2b = 63.")

    seat_count = int(box_count) // 3
    bar_depth = 10.0
    gap = 10.0
    if bar_count is None:
        bar_width = bar_depth
        bar_count = int((length + gap) // (bar_width + gap))
        if bar_count < 1:
            raise ValueError("length is too small for a grid bar.")
        bar_span = bar_count * bar_width + (bar_count - 1) * gap
        side_margin = (length - bar_span) / 2.0
    else:
        bar_count = int(bar_count)
        available_bar_width = length - (bar_count - 1) * gap
        if available_bar_width <= 0:
            max_bar_count = int(math.ceil(length / gap))
            raise ValueError(
                "bar_count is too large for 10 cm gaps across length; use no more than "
                f"{max_bar_count} bars."
            )
        bar_width = available_bar_width / bar_count
        side_margin = 0.0
    if bar_width <= 0:
        raise ValueError(
            "The requested bar_count leaves no room for bars between the 10 cm gaps."
        )
    grid_y = seat_count * 3.0 * tread_depth
    grid_height = seat_count * 3.0 * riser_height + 100.0

    bars = []
    for index in range(bar_count):
        bar = create_box(origin, bar_width, bar_depth, grid_height)
        transform = rg.Transform.Translation(
            rg.Vector3d(
                side_margin + index * (bar_width + gap),
                grid_y,
                0,
            )
        )
        if not bar.Transform(transform):
            raise RuntimeError("Could not move a staircase grid bar.")
        bars.append(bar)

    return bars

