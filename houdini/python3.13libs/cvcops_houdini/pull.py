"""Distort's pull of frame B onto A's grid, for the M4 row and the carry example.

Pure hou-free Python: it builds nodes in a parent the caller owns, imports neither hou nor cv2, and runs nothing at
import. `pull_network` is what houdini/tests/bake_once.py --mode pull and the M4 example both use.
"""

SCALE = -1.0              # P4: Scale -1 is the pull direction, with no second conversion
STEP_MODE = 0             # Pixels per Step off: matches cv2.remap to 0.003 levels (FACTS H38)
FILTER = "bilinear"


def pull_network(parent, b, flow, name="pull"):
    """Wire B and the asset's converted flow into one Distort that pulls B onto A's grid.

    Args:
        parent: a Copernicus network node (an object with createNode).
        b: the node holding frame B.
        flow: the node whose output 0 is the asset's Flow (UV, Houdini image units).
        name: the new node's name.

    Returns:
        The Distort node. One lookup at p + f, bilinear, no second conversion.
    """
    node = parent.createNode("distort", name)
    node.setInput(0, b, 0)
    node.setInput(1, flow, 0)
    node.parm("scale").set(SCALE)
    node.parm("scalebytimeinc").set(0)
    node.parm("usecfl").set(STEP_MODE)
    node.parm("filter").set(FILTER)
    return node
