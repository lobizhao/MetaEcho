import maya.cmds as cmds
import pymel.core as pm
import numpy as np
from scipy.spatial.distance import cdist
import math
import maya.OpenMaya as OpenMaya
from maya.OpenMaya import MSpace

class MetaEchoFullToolbox(object):
    def __init__(self):
        self.window_name = "MetaEcho_Integrated_Toolbox"
        self.feature_Matrix = None
        self.feature_norms = None
        self.theta = None

    def show(self):
        if cmds.window(self.window_name, exists=True):
            cmds.deleteUI(self.window_name)

        self.window = cmds.window(self.window_name, title="MetaEcho Integrated Toolbox", widthHeight=(380, 500))
        tabs = cmds.tabLayout(innerMarginWidth=5, innerMarginHeight=5)
        
        # Tab 1: Skeleton
        tab1 = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
        self.build_namespace_ui()
        cmds.setParent('..')

        # Tab 2: RBF Tool
        tab2 = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
        self.build_rbf_ui()
        cmds.setParent('..')

        # Tab 3: Utils
        tab3 = cmds.columnLayout(adjustableColumn=True, rowSpacing=10)
        self.build_utils_ui()
        cmds.setParent('..')

        cmds.tabLayout(tabs, edit=True, tabLabel=((tab1, 'Skeleton'), (tab2, 'RBF Tool'), (tab3, 'Weights/Utils')))
        cmds.showWindow(self.window)

    # --- UI Helpers ---
    def build_namespace_ui(self):
        cmds.separator(h=10, style='none')
        cmds.text("Namespace Management", font="boldLabelFont")
        self.tf_ns_prefix = cmds.textFieldGrp(label="Prefix/NS:", text="MHHead:", columnWidth2=[80, 240])
        cmds.button(label="Apply Prefix to Selected", h=35, bgc=[0.3, 0.4, 0.5], command=self.apply_prefix_logic)
        cmds.button(label="Remove Namespace from Selected", h=30, command=self.remove_namespace_logic)
        cmds.separator(h=15)
        cmds.text("Joint Constraints (MH to Target)", font="boldLabelFont")
        self.tf_src_ns = cmds.textFieldGrp(label="Source NS:", text="MHHead:", columnWidth2=[80, 240])
        self.tf_root_jnt = cmds.textFieldGrp(label="Root Joint:", text="spine_04", columnWidth2=[80, 240])
        cmds.button(label="Run Joint Constraint Logic", h=40, bgc=[0.4, 0.5, 0.3], command=self.run_constraint_logic)

    def build_rbf_ui(self):
        cmds.separator(h=10, style='none')
        cmds.text("RBF Mesh & Skeleton Deformation", font="boldLabelFont")
        self.tf_source = cmds.textFieldButtonGrp(label="Source Mesh:", bl="Load", bc=self.load_source, columnWidth3=[80, 200, 50])
        self.tf_target = cmds.textFieldButtonGrp(label="Target Mesh:", bl="Load", bc=self.load_target, columnWidth3=[80, 200, 50])
        cmds.button(label="Build RBF Solver", h=45, bgc=[0.2, 0.4, 0.6], command=self.build_solver_logic)
        cmds.separator(h=5)
        cmds.button(label="Retarget Skeleton (Select Root)", h=35, command=self.retarget_skel_logic)
        cmds.button(label="Retarget Accessory Mesh", h=35, command=self.retarget_mesh_logic)

    def build_utils_ui(self):
        cmds.separator(h=10, style='none')
        cmds.text("Quick Native Tools", font="boldLabelFont")
        cmds.button(label="Open Copy Skin Weights Options", h=50, bgc=[0.8, 0.5, 0.2], 
                    command=lambda *x: cmds.runTimeCommand("CopySkinWeightsOptions", edit=True) or cmds.CopySkinWeightsOptions())
        cmds.text("Usage: Select Source Mesh then Target Mesh,\nthen click above to copy weights.", align="center")

    # --- Namespace Logic ---
    def apply_prefix_logic(self, *args):
        prefix = cmds.textFieldGrp(self.tf_ns_prefix, q=True, text=True)
        sel = cmds.ls(sl=True, long=True)
        if not sel: return
        sel.sort(key=len, reverse=True)
        for obj in sel:
            short_name = obj.split("|")[-1].split(":")[-1]
            cmds.rename(obj, prefix + short_name)

    def remove_namespace_logic(self, *args):
        selected_objs = cmds.ls(selection=True, long=True)
        if not selected_objs: return
        selected_objs.sort(key=lambda x: x.count('|'), reverse=True)
        for obj in selected_objs:
            short_name = obj.split("|")[-1]
            if ":" in short_name:
                cmds.rename(obj, short_name.split(":")[-1])

    def run_constraint_logic(self, *args):
        src_ns = cmds.textFieldGrp(self.tf_src_ns, q=True, text=True)
        root_name = cmds.textFieldGrp(self.tf_root_jnt, q=True, text=True)
        src_root = src_ns + root_name
        if not cmds.objExists(src_root): return
        all_src_jnts = cmds.listRelatives(src_root, ad=True, type="joint", f=True) or []
        all_src_jnts.append(src_root)
        for src_path in all_src_jnts:
            base_name = src_path.split("|")[-1].replace(src_ns, "")
            if cmds.objExists(base_name):
                old = cmds.listConnections(base_name, type="constraint")
                if old: cmds.delete(old)
                cmds.parentConstraint(src_path, base_name, mo=True, weight=1)

    # --- RBF Math Utils ---
    def get_radius(self, objects):
        dag_node = OpenMaya.MFnDagNode(objects[0])
        bounding_box = dag_node.boundingBox()
        for i in range(1, len(objects)):
            dag = OpenMaya.MFnDagNode(objects[i])
            bounding_box.expand(dag.boundingBox())
        center = bounding_box.center()
        max_bb = bounding_box.max()
        radius = math.sqrt(sum((center[i] - max_bb[i])**2 for i in range(3)))
        return radius, center

    def points_on_sphere(self, num, scale, center):
        out_points = OpenMaya.MFloatPointArray(num)
        inc = math.pi * (3.0 - math.sqrt(5.0))
        off = 2.0 / num
        for i in range(num):
            y = i * off - 1.0 + (off / 2.0)
            r = math.sqrt(1.0 - y * y)
            phi = i * inc
            out_points.set(i, center[0] + scale * math.cos(phi) * r, center[1] + scale * y, center[2] + scale * math.sin(phi) * r)
        return out_points

    def build_sphere(self, src_path, tgt_path, num):
        src_radius, src_center = self.get_radius([src_path])
        tgt_radius, tgt_center = self.get_radius([tgt_path])
        max_r = max(src_radius, tgt_radius) * 3.0
        return self.points_on_sphere(num, max_r, src_center), self.points_on_sphere(num, max_r, tgt_center)

    # --- RBF Core Logic ---
    def load_source(self, *args):
        sel = cmds.ls(sl=True)
        if sel: cmds.textFieldButtonGrp(self.tf_source, e=True, text=sel[0])

    def load_target(self, *args):
        sel = cmds.ls(sl=True)
        if sel: cmds.textFieldButtonGrp(self.tf_target, e=True, text=sel[0])

    def rbf_calculate(self, input_pos):
        norm_input = input_pos.copy()
        for i in range(3):
            if self.feature_norms[i] != 0: norm_input[i] /= self.feature_norms[i]
        input_dist = cdist([norm_input], self.feature_Matrix, "euclidean")
        return np.matmul(self.theta, input_dist.T).T[0]

    #for RBF section
    def build_solver_logic(self, *args):
        src = cmds.textFieldButtonGrp(self.tf_source, q=True, text=True)
        tgt = cmds.textFieldButtonGrp(self.tf_target, q=True, text=True)
        if not src or not tgt: return

        src_vtx_count = cmds.polyEvaluate(src, v=1)
        tgt_vtx_count = cmds.polyEvaluate(tgt, v=1)
        if src_vtx_count != tgt_vtx_count: 
            cmds.error("Vertex count mismatch!")
            return

        src_shape = cmds.listRelatives(src, s=1)[0]
        tgt_shape = cmds.listRelatives(tgt, s=1)[0]
        src_path = pm.PyNode(src_shape).__apimdagpath__()
        tgt_path = pm.PyNode(tgt_shape).__apimdagpath__()
        extra_src, extra_tgt = self.build_sphere(src_path, tgt_path, 300)

        dim = src_vtx_count + 300
        self.feature_Matrix = np.zeros([dim, 3])
        outputs_Matrix = np.zeros([dim, 3])

        for i in range(src_vtx_count):
            self.feature_Matrix[i] = cmds.pointPosition(f"{src}.vtx[{i}]", w=1)
            outputs_Matrix[i] = cmds.pointPosition(f"{tgt}.vtx[{i}]", w=1)
        for i in range(300):
            idx = i + src_vtx_count
            self.feature_Matrix[idx] = [extra_src[i].x, extra_src[i].y, extra_src[i].z]
            outputs_Matrix[idx] = [extra_tgt[i].x, extra_tgt[i].y, extra_tgt[i].z]

        self.feature_norms = np.linalg.norm(self.feature_Matrix, ord=1, axis=0)
        self.feature_Matrix = self.feature_Matrix / self.feature_norms
        dist_mat = cdist(self.feature_Matrix, self.feature_Matrix, "euclidean")
        self.theta = np.matmul(np.linalg.inv(dist_mat), outputs_Matrix).T
        
        cmds.confirmDialog(title='Success', message='RBF Solver Build Success!')

    def retarget_skel_logic(self, *args):
        if self.theta is None: 
            cmds.error("请先点击 Build Solver 生成计算矩阵！")
            return
            
        root = cmds.ls(sl=True, type="joint")
        if not root: 
            cmds.error("请先选中骨骼的 Root Joint！")
            return
        
        cmds.duplicate(root[0])
        cmds.select(cmds.ls(sl=True, type="joint")[0], hi=True)
        jnt_list = cmds.ls(sl=True, type="joint")

        for i in range(len(jnt_list)):
            ori_pos = cmds.xform(jnt_list[i], q=1, ws=1, t=1)
            input_pos = np.array([ori_pos[0], ori_pos[1], ori_pos[2]])
            
            output = self.rbf_calculate(input_pos) 
            
            new_pos = ori_pos
            new_pos[0] = output[0]
            new_pos[1] = output[1]
            new_pos[2] = output[2]
            
            cmds.joint(jnt_list[i], edit=True, p=new_pos, co=1)
            
        print("Skeleton Retargeting Done.")

    def retarget_mesh_logic(self, *args):
        if self.theta is None: return
        sel = cmds.ls(sl=True)
        if not sel: return
        
        mesh = cmds.duplicate(sel[0], name=f"{sel[0]}_Retargeted")[0]
        m_sel = OpenMaya.MSelectionList()
        m_sel.add(mesh)
        path = OpenMaya.MDagPath()
        m_sel.getDagPath(0, path)
        
        m_mesh = OpenMaya.MFnMesh(path)
        vtx_it = OpenMaya.MItMeshVertex(path)
        new_points = OpenMaya.MPointArray()

        while not vtx_it.isDone():
            p = vtx_it.position(MSpace.kWorld)
            new_p_val = self.rbf_calculate(np.array([p.x, p.y, p.z]))
            new_points.append(OpenMaya.MPoint(new_p_val[0], new_p_val[1], new_p_val[2]))
            vtx_it.next()
            
        m_mesh.setPoints(new_points, MSpace.kWorld)
        print("Mesh Retargeting Done.")

# Run Tool
tool = MetaEchoFullToolbox()
tool.show()