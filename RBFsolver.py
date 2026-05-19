import maya.cmds as cmds
import pymel.core as pm
import numpy as np
import math
import maya.OpenMaya as OpenMaya
from maya.OpenMaya import MSpace
from scipy.spatial.distance import cdist

# NOTE: util methods to increase robust
def build_sphere(source_object, target_object, length, source_lists=[]):
    # insert some points data to fix global effect
    source_lists.append(source_object)

    # NOTE: get sphere radius
    source_radius, source_center = get_radius(source_lists)
    target_radius, target_center = get_radius([target_object])

    max_radius = max(source_radius, target_radius)
    max_radius *= 3.0

    out_source_points = points_on_sphere(length, max_radius, source_center)
    out_target_points = points_on_sphere(length, max_radius, target_center)

    return out_source_points, out_target_points


def get_radius(objects):
    if len(objects) == 0:
        return
    # NOTE: merge objects bouding box
    try:
        dag_node = OpenMaya.MFnDagNode(objects[0])
    except:
        cmds.error("dag_node error!")
        raise
    bounding_box = dag_node.boundingBox()

    index = 1
    while index < len(objects):
        dag = OpenMaya.MFnDagNode(objects[index])
        bounding_box.expand(dag.boundingBox())
        index += 1

    center_bb = bounding_box.center()
    max_bb = bounding_box.max()
    radius = math.sqrt(
        (center_bb[0] - max_bb[0]) * (center_bb[0] - max_bb[0])
        + (center_bb[1] - max_bb[1]) * (center_bb[1] - max_bb[1])
        + (center_bb[2] - max_bb[2]) * (center_bb[2] - max_bb[2])
    )

    return radius, center_bb


def points_on_sphere(num, scale, center_point):
    # NOTE: scale can be three dim
    out_points = OpenMaya.MFloatPointArray(num)
    pi = math.pi
    inc = pi * (3.0 - math.sqrt(5.0))
    off = 2.0 / num

    index = 0
    while index < num:
        y = index * off - 1.0 + (off / 2.0)
        r = math.sqrt(1.0 - y * y)
        phi = index * inc
        out_points.set(
            index,
            (center_point[0] + scale * math.cos(phi) * r),
            (center_point[1] + scale * y),
            (center_point[2] + scale * math.sin(phi) * r),
        )
        index += 1

    return out_points


def getDagPath():
    mSelList = OpenMaya.MSelectionList()
    OpenMaya.MGlobal.getActiveSelectionList(mSelList)
    sel = OpenMaya.MItSelectionList(mSelList)
    path = OpenMaya.MDagPath()
    sel.getDagPath(path)
    return path


# ==========================================
# UI Helper Functions
# ==========================================
def load_source(*args):

    sel = cmds.ls(sl=True)
    if sel:
        cmds.textField("tf_source", edit=True, text=sel[0])
    else:
        cmds.warning("Please select a Source Mesh first!")

def load_target(*args):

    sel = cmds.ls(sl=True)
    if sel:
        cmds.textField("tf_target", edit=True, text=sel[0])
    else:
        cmds.warning("Please select a Target Mesh first!")


# ==========================================
# Core Functions
# ==========================================
def buildSolver(*args):

    src_mesh = cmds.textField("tf_source", query=True, text=True)
    tgt_mesh = cmds.textField("tf_target", query=True, text=True)

    if not src_mesh or not tgt_mesh:
        cmds.error("Please load both Source and Target Meshes in the UI!")

    select_list = [src_mesh, tgt_mesh]

    src_vtx = cmds.polyEvaluate(select_list[0], v=1)
    tgt_vtx = cmds.polyEvaluate(select_list[1], v=1)
    
    if src_vtx != tgt_vtx or src_vtx < 3:
        cmds.error("Source and target Mesh must have same vertex count")

    # add 300 points
    src_shape = cmds.listRelatives(select_list[0], s=1, c=1)[0]
    tgt_shape = cmds.listRelatives(select_list[1], s=1, c=1)[0]
    src_path = pm.PyNode(src_shape).__apimdagpath__()
    tgt_path = pm.PyNode(tgt_shape).__apimdagpath__()
    extra_vert_list, extra_vert_list_tgt = build_sphere(src_path, tgt_path, 300)

    # make featureMatrix and normalize
    dim = src_vtx + 300
    vert_list = cmds.ls("%s.vtx[:]" % select_list[0], fl=True)
    vert_list_tgt = cmds.ls("%s.vtx[:]" % select_list[1], fl=True)
    global feature_Matrix
    feature_Matrix = np.zeros([dim, 3])
    outputs_Matrix = np.zeros([dim, 3])
    
    for ii in range(src_vtx):
        feature_Matrix[ii] = cmds.pointPosition(vert_list[ii], w=1)
        outputs_Matrix[ii] = cmds.pointPosition(vert_list_tgt[ii], w=1)
        
    for ii in range(300):
        feature_Matrix[ii + src_vtx][0] = extra_vert_list[ii].x
        feature_Matrix[ii + src_vtx][1] = extra_vert_list[ii].y
        feature_Matrix[ii + src_vtx][2] = extra_vert_list[ii].z
        outputs_Matrix[ii + src_vtx][0] = extra_vert_list_tgt[ii].x
        outputs_Matrix[ii + src_vtx][1] = extra_vert_list_tgt[ii].y
        outputs_Matrix[ii + src_vtx][2] = extra_vert_list_tgt[ii].z

    # Normalize
    global feature_norms
    feature_norms = np.array(
        [
            np.linalg.norm(feature_Matrix[:, i], ord=1)
            for i in range(feature_Matrix.shape[1])
        ]
    )
    feature_Matrix = feature_Matrix / feature_norms

    # calculate distanceMatrix
    global distanceMatrix
    distanceMatrix = np.zeros([dim, dim])
    distanceMatrix = cdist(feature_Matrix, feature_Matrix, "euclidean")

    global theta
    theta = np.matmul(np.linalg.inv(distanceMatrix), outputs_Matrix).T
    cmds.confirmDialog(title='Success', message='RBF Solver Build Completed!', button=['OK'], defaultButton='OK')


def RBFSolver(input_pos):
    # calculate input distance vector
    for i in range(input_pos.shape[0]):
        if feature_norms[i] != 0.0:
            input_pos[i] /= feature_norms[i]

    input_distance = cdist([input_pos], feature_Matrix, "euclidean")
    output = np.matmul(theta, input_distance.T).reshape(1, input_pos.shape[0])

    return output


def retargetSkel(*args):
    # check select
    root = cmds.ls(sl=1, type="joint")
    if not root:
        cmds.error("Please select the Root Joint first!")

    cmds.duplicate(root)

    # get joint list
    root = cmds.ls(sl=1, type="joint")
    cmds.select(root, hi=1)
    jnt_list = cmds.ls(sl=1, type="joint")

    for i in range(len(jnt_list)):
        ori_pos = cmds.xform(jnt_list[i], q=1, ws=1, t=1)
        input_pos = np.array([ori_pos[0], ori_pos[1], ori_pos[2]])
        output = RBFSolver(input_pos)
        new_pos = ori_pos
        new_pos[0] = output[0][0]
        new_pos[1] = output[0][1]
        new_pos[2] = output[0][2]
        cmds.joint(jnt_list[i], edit=True, p=new_pos, co=1)


def retargetMesh(*args):
    # check select
    select_list = []
    if cmds.ls(sl=True) != []:
        select_list = cmds.ls(sl=True)
        item = select_list[0]
    else:
        cmds.error("Please select a Mesh to retarget!")

    cmds.duplicate(item)

    # Get selected object
    path = getDagPath()

    # Attach to MFnMesh
    MFnMesh = OpenMaya.MFnMesh(path)
    itr = OpenMaya.MItMeshVertex(path)

    # Create empty point array to store new points
    newPointArray = OpenMaya.MPointArray()

    while not itr.isDone():
        newPoint = itr.position(MSpace.kObject)
        input_pos = np.array([newPoint.x, newPoint.y, newPoint.z])
        output = RBFSolver(input_pos)
        newPoint.x = output[0][0]
        newPoint.y = output[0][1]
        newPoint.z = output[0][2]
        newPointArray.append(newPoint)
        itr.next()

    # Set new points to mesh all at once
    MFnMesh.setPoints(newPointArray)


# ==========================================
# Main GUI Window
# ==========================================
def mainGUI():
    windowName = "RBF_Learn"
    windowTitle = "MetaEcho RBF Tool"
    
    if cmds.window(windowName, exists=True):
        cmds.deleteUI(windowName)
        
    cmds.window(windowName, title=windowTitle, w=320, h=250)
    cmds.columnLayout(adj=True, rowSpacing=10, columnAttach=('both', 10))
    
    cmds.separator(style='none', h=5)
    cmds.text(label="1. Setup Source & Target Meshes", font="boldLabelFont", align="left")
    
    # ------------------
    # Source UI Row
    # ------------------
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(50, 180, 60), adjustableColumn=2)
    cmds.text(label="Source:")

    cmds.textField("tf_source", editable=False, text="")
    cmds.button(label="Select", command=load_source)
    cmds.setParent('..')
    
    # ------------------
    # Target UI Row
    # ------------------
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(50, 180, 60), adjustableColumn=2)
    cmds.text(label="Target:")
  
    cmds.textField("tf_target", editable=False, text="")
    cmds.button(label="Select", command=load_target)
    cmds.setParent('..')

    # ------------------
    # Buttons
    # ------------------
    cmds.separator()
    cmds.button(l="Build Solver", h=40, bgc=[0.2, 0.4, 0.6], c=buildSolver)
    
    cmds.separator()
    cmds.text(label="2. Apply RBF Deformation", font="boldLabelFont", align="left")
    
    cmds.button(l="Retarget Skeleton (Select Root Joint)", h=40, c=retargetSkel)
    cmds.button(l="Retarget Accessories Mesh (Select Mesh)", h=40, c=retargetMesh)
    
    cmds.separator(style='none', h=5)

    cmds.showWindow(windowName)

mainGUI()