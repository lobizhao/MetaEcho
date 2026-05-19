import maya.cmds as cmds

SOURCE_NS = "MHHead:"
TARGET_NS = ""
ROOT_JOINT = "spine_04"

print("in processing")

src_root = SOURCE_NS + ROOT_JOINT
if not cmds.objExists(src_root):
    cmds.error(f"can not found root: {src_root}")

all_src_jnts = cmds.listRelatives(src_root, ad=True, type="joint", f=True) or []
all_src_jnts.append(src_root)

success_count = 0

for src_path in all_src_jnts:
    short_name = src_path.split("|")[-1]
    base_name = short_name.replace(SOURCE_NS, "")
    
    tgt_jnt = TARGET_NS + base_name
    
    if cmds.objExists(tgt_jnt):
        old_constraints = cmds.listConnections(tgt_jnt, type="constraint")
        if old_constraints:
            cmds.delete(old_constraints)
        try:
            cmds.parentConstraint(src_path, tgt_jnt, mo=True, weight=1)
            # cmds.scaleConstraint(src_path, tgt_jnt, mo=True, weight=1)
            success_count += 1
        except:
            pass

print(f"done{success_count}")
