import maya.cmds as cmds

def apply_prefix(*args):
    prefix = cmds.textField("tf_namespace_prefix", query=True, text=True)
    
    if not prefix:
        cmds.warning("Please enter a prefix or namespace! (e.g., 'OldMan:')")
        return
        
    sel = cmds.ls(sl=True, long=True)
    if not sel:
        cmds.warning("Please select the joints you want to rename!")
        return
        
    if ":" in prefix:
        ns = prefix.split(":")[0]
        if not cmds.namespace(exists=ns):
            cmds.namespace(add=ns)
            print(f"Created missing namespace: {ns}")
            
    sel.sort(key=len, reverse=True)
    
    count = 0
    for obj in sel:
        short_name = obj.split("|")[-1]
        
        if ":" in short_name:
            short_name = short_name.split(":")[-1]
            
        new_name = prefix + short_name
        
        try:
            cmds.rename(obj, new_name)
            count += 1
        except Exception as e:
            print(f"Failed to rename {obj}. Error: {e}")
            
    cmds.confirmDialog(title='Success', message=f'Successfully updated {count} objects!', button=['OK'])

def show_namespace_ui():
    window_name = "NamespaceFixerUI"
    
    if cmds.window(window_name, exists=True):
        cmds.deleteUI(window_name)
        
    cmds.window(window_name, title="Namespace Fixer", widthHeight=(320, 150))
    cmds.columnLayout(adjustableColumn=True, rowSpacing=10, columnAttach=('both', 15))
    
    cmds.separator(height=10, style='none')
    cmds.text(label="Enter Namespace (e.g., 'OldMan:') or Prefix:", font="boldLabelFont", align="left")
    
    cmds.textField("tf_namespace_prefix", text="", placeholderText="Example: MetaHuman:")
    
    cmds.button(label="Apply to Selected", height=40, backgroundColor=(0.2, 0.6, 0.4), command=apply_prefix)
    
    cmds.separator(height=10, style='none')
    
    cmds.showWindow(window_name)

show_namespace_ui()