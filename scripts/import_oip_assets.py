"""Run with Blender --background --python. Converts upstream GLB meshes to Unity FBX.

Only recenters and converts existing geometry; no downloaded scripts are executed.
"""
import hashlib
import json
from pathlib import Path
import subprocess

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / ".cache/upstream/oip"
OUT = ROOT / "unity/Assets/Resources/Industrial"
OUT.mkdir(parents=True, exist_ok=True)
SOURCES = ["Gantry/Gantry.glb", "BladeStop/BladeStop.glb", "DiffuseSensor.glb", "Pallet.glb",
           "ChainTransfer/ChainTransfer.glb", "LegsBar.glb", "LegsSide.glb", "ConveyorRollerEnd.glb"]
manifest = {"repository": "https://github.com/Open-Industry-Project/Open-Industry-Project",
            "commit": subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip(),
            "license": "MIT", "conversion": "Blender GLB import, recenter existing meshes, FBX export; no original textures", "assets": []}
for rel in SOURCES:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    src = UPSTREAM / "assets/3DModels" / rel
    bpy.ops.import_scene.gltf(filepath=str(src))
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for obj in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        mesh = obj.data.copy()
        mesh.transform(obj.matrix_world)
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.data = mesh
        coords = [v.co for v in mesh.vertices]
        lo = Vector(tuple(min(v[a] for v in coords) for a in range(3)))
        hi = Vector(tuple(max(v[a] for v in coords) for a in range(3)))
        center = (lo + hi) * .5
        mesh.transform(Matrix.Translation(-center))
        mesh.materials.clear()
        name = Path(rel).stem + "_" + obj.name.replace(".", "_")
        path = OUT / (name + ".fbx")
        bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"MESH"},
                                 add_leaf_bones=False, bake_anim=False, axis_forward="-Z", axis_up="Y",
                                 apply_unit_scale=True, use_mesh_modifiers=True)
        size = hi - lo
        manifest["assets"].append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                                    "source": "assets/3DModels/" + rel, "node": obj.name,
                                    "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                    "unity_size_m": [size.x, size.z, size.y]})
notices = ROOT / "third_party"
notices.mkdir(exist_ok=True)
(notices / "oip-assets.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
(notices / "OIP-LICENSE.txt").write_bytes((UPSTREAM / "LICENSE").read_bytes())
print("EXPORTED", len(manifest["assets"]), "existing meshes")
