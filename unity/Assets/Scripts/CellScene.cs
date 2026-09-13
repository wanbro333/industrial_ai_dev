using System.Collections.Generic;
using UnityEngine;

namespace IndustrialCell
{
    /// <summary>Assembles reused OIP geometry and binds it to measured device positions.</summary>
    [RequireComponent(typeof(MqttBridge))]
    public sealed class CellScene : MonoBehaviour
    {
        private DeviceModel model;
        private Camera cameraView;
        private Transform carrier, stopper, divider, lifter, tool, secondCylinder, piston1, piston2;
        private readonly Dictionary<string, Transform> materialObjects = new Dictionary<string, Transform>();
        private readonly List<Transform> beltMarks = new List<Transform>();
        private Renderer[] lamps = new Renderer[3];
        private Material steel, dark, teal, rubber, blue, yellow, white, red;
        private Vector3 lookAt = new Vector3(0, 1.0f, .7f);
        private float yaw = -35, pitch = 37, distance = 11;
        private int previousStatus = -1;
        private float lampPhase;

        private void Start()
        {
            model = GetComponent<MqttBridge>().Model;
            steel = Mat("Powder coated aluminum", new Color(.62f,.69f,.68f), .45f);
            dark = Mat("Machine graphite", new Color(.17f,.24f,.25f), .3f);
            teal = Mat("Safety teal", new Color(.05f,.43f,.36f), .1f);
            rubber = Mat("Conveyor rubber", new Color(.20f,.27f,.26f));
            blue = Mat("Blue lid", new Color(.06f,.42f,.71f));
            yellow = Mat("Yellow lid", new Color(.97f,.66f,.12f));
            white = Mat("Markings", new Color(.9f,.95f,.9f));
            red = Mat("Red lamp", new Color(.82f,.15f,.12f));
            BuildCell();
            SetCamera("overview");
        }

        private Material Mat(string label, Color color, float metal = 0)
        {
            var material = new Material(Shader.Find("Standard")) { name = label, color = color };
            material.SetFloat("_Metallic", metal);
            material.SetFloat("_Glossiness", .28f);
            return material;
        }

        private Transform Part(string asset, string label, Vector3 position, Vector3 size, Material material)
        {
            var prefab = Resources.Load<GameObject>("Industrial/" + asset);
            if (prefab == null) throw new System.InvalidOperationException("Missing reused industrial asset: " + asset);
            var root = new GameObject(label).transform;
            var instance = Instantiate(prefab, root);
            var renderers = instance.GetComponentsInChildren<Renderer>();
            var bounds = new Bounds(Vector3.zero, Vector3.zero);
            bool first = true;
            foreach (var renderer in renderers)
            {
                if (first) { bounds = renderer.bounds; first = false; } else bounds.Encapsulate(renderer.bounds);
                var mats = renderer.sharedMaterials;
                for (int n = 0; n < mats.Length; n++) mats[n] = material;
                renderer.sharedMaterials = mats;
            }
            instance.transform.position -= bounds.center;
            root.localScale = new Vector3(size.x / Mathf.Max(bounds.size.x,.001f),
                size.y / Mathf.Max(bounds.size.y,.001f), size.z / Mathf.Max(bounds.size.z,.001f));
            root.position = position;
            return root;
        }

        // Only functional surfaces, indicator marks and workpieces use primitives.
        // Structural/moving equipment meshes below are converted upstream OIP assets.
        private Transform Surface(string name, Vector3 position, Vector3 size, Material material,
                                  PrimitiveType shape = PrimitiveType.Cube)
        {
            var obj = GameObject.CreatePrimitive(shape);
            obj.name = name;
            obj.transform.position = position;
            obj.transform.localScale = size;
            obj.GetComponent<Renderer>().sharedMaterial = material;
            Destroy(obj.GetComponent<Collider>());
            return obj.transform;
        }

        private void Label(string text, Vector3 position, float size = .17f)
        {
            var obj = new GameObject(text);
            obj.transform.position = position;
            obj.transform.rotation = Quaternion.Euler(90, 0, 0);
            var label = obj.AddComponent<TextMesh>();
            label.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            obj.GetComponent<MeshRenderer>().sharedMaterial = label.font.material;
            label.text = text; label.characterSize = size; label.fontSize = 48;
            label.anchor = TextAnchor.MiddleCenter; label.color = new Color(.28f,.42f,.35f);
        }

        private void BuildCell()
        {
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(.70f,.76f,.73f);
            var light = new GameObject("Soft daylight").AddComponent<Light>();
            light.type = LightType.Directional; light.intensity = 1.15f;
            light.shadows = LightShadows.Soft; light.shadowStrength = .45f;
            light.transform.rotation = Quaternion.Euler(50,-30,0);
            var floor = Mat("Workshop floor", new Color(.85f,.9f,.86f));
            Surface("Floor",new Vector3(0,-.06f,0),new Vector3(28,.1f,22),floor);
            var grid = Mat("Floor grid",new Color(.79f,.85f,.80f));
            for(int n=-10;n<=10;n++)
            {
                Surface("Grid X",new Vector3(n,0,0),new Vector3(.008f,.002f,20),grid);
                Surface("Grid Z",new Vector3(0,0,n),new Vector3(20,.002f,.008f),grid);
            }
            // Belt support, side rails, terminal rollers and feet reuse industrial components.
            Surface("Belt surface",new Vector3(0,.96f,0),new Vector3(7.7f,.06f,.8f),rubber);
            for(int side=-1;side<=1;side+=2)
            {
                Part("Gantry_Beam_Main","Conveyor rail",new Vector3(0,.92f,side*.52f),new Vector3(8,.23f,.13f),steel);
                for(int n=0;n<3;n++)
                {
                    float x=-3.25f+n*3.25f;
                    Part("Gantry_Leg_Main","Conveyor support",new Vector3(x,.44f,side*.53f),new Vector3(.10f,.88f,.10f),steel);
                    Part("Gantry_Leg_Base","Adjustable foot",new Vector3(x,.065f,side*.53f),new Vector3(.21f,.13f,.21f),dark);
                }
            }
            for(int side=-1;side<=1;side+=2)
                Part("ConveyorRollerEnd_ConvRollerEnd","End roller",new Vector3(side*3.9f,.91f,0),new Vector3(.2f,.23f,1.05f),dark);
            for(int n=0;n<22;n++) beltMarks.Add(Surface("Belt seam",new Vector3(n*.35f-3.85f,1.001f,0),new Vector3(.013f,.002f,.77f),dark));
            Part("BladeStop_BaseMiddle","Stop cylinder base",new Vector3(.6f,.74f,0),new Vector3(.16f,.25f,.86f),steel);
            stopper=Part("BladeStop_BladeMiddle","Stop blade",new Vector3(.6f,1.05f,0),new Vector3(.065f,.12f,.8f),teal);
            Part("BladeStop_BaseMiddle","Divider base",new Vector3(-2.8f,.74f,0),new Vector3(.15f,.25f,.86f),steel);
            divider=Part("BladeStop_BladeMiddle","Divider blade",new Vector3(-2.8f,1.05f,0),new Vector3(.065f,.12f,.8f),teal);
            lifter=Part("ChainTransfer_Base","Lift platform",new Vector3(.6f,.97f,0),new Vector3(.5f,.06f,.56f),steel);
            for(int n=0;n<2;n++)
            {
                float x=n==0?-1.8f:.6f;
                Part("DiffuseSensor_Body","Presence sensor",new Vector3(x,1.08f,-.64f),new Vector3(.11f,.14f,.13f),teal);
                Part("DiffuseSensor_Connector","Sensor connector",new Vector3(x,1.04f,-.77f),new Vector3(.04f,.07f,.06f),dark);
                Surface("Sensing beam",new Vector3(x,1.075f,0),new Vector3(.014f,.01f,1.15f),Mat("Sensor beam "+n,new Color(.4f,.77f,.65f)));
            }
            // Gantry frame spans the pickup and both bin positions.
            for(int n=0;n<2;n++)
            {
                float z=n==0?-.85f:3.25f;
                Part("Gantry_Leg_Main","Gantry upright",new Vector3(1.15f,1.43f,z),new Vector3(.15f,2.86f,.15f),steel);
                Part("Gantry_Leg_Base","Gantry foot",new Vector3(1.15f,.08f,z),new Vector3(.36f,.16f,.36f),dark);
            }
            Part("Gantry_Beam_Main","Gantry crossbeam",new Vector3(1.15f,2.87f,1.2f),new Vector3(.2f,.2f,4.2f),steel);
            Part("BladeStop_AirPressureL","Translation cylinder 1",new Vector3(.6f,2.7f,.38f),new Vector3(.19f,.17f,.95f),dark);
            piston1=Part("Gantry_Beam_Lift","Translation piston 1",new Vector3(.6f,2.7f,.7f),new Vector3(.045f,.045f,.1f),steel);
            secondCylinder=Part("BladeStop_AirPressureR","Translation cylinder 2",new Vector3(.6f,2.45f,.3f),new Vector3(.18f,.17f,.95f),teal);
            piston2=Part("Gantry_Beam_Lift","Translation piston 2",new Vector3(.6f,2.45f,.7f),new Vector3(.045f,.045f,.1f),steel);
            tool=Part("Gantry_Tool_01","Gripper and vertical slide",new Vector3(.6f,2.0f,0),new Vector3(.27f,.45f,.3f),dark);
            // Separate jaws represent open/close; they are also reused blade corners.
            var jawLeft=Part("BladeStop_BladeCornerL","Jaw left",Vector3.zero,new Vector3(.05f,.12f,.22f),steel);
            var jawRight=Part("BladeStop_BladeCornerR","Jaw right",Vector3.zero,new Vector3(.05f,.12f,.22f),steel);
            jawLeft.SetParent(tool,true); jawRight.SetParent(tool,true);
            for(int n=1;n<=2;n++)
            {
                float z=n*1.25f;
                Part("ChainTransfer_Container","Bin "+n,new Vector3(.6f,1.06f,z),new Vector3(.85f,.27f,.88f),n==1?yellow:blue);
                Part("Gantry_Leg_Main","Bin support",new Vector3(.6f,.50f,z),new Vector3(.14f,1,.14f),steel);
                Part("Gantry_Leg_Base","Bin base",new Vector3(.6f,.07f,z),new Vector3(.60f,.14f,.6f),dark);
                Label("NG 0"+n,new Vector3(-.15f,.012f,z));
            }
            carrier=Part("Pallet_WoodPallet","Work carrier",new Vector3(-3.7f,1.05f,0),new Vector3(.45f,.065f,.52f),steel);
            carrier.gameObject.SetActive(false);
            for(int n=0;n<3;n++)
            {
                var lamp=Surface("Tower lamp "+n,new Vector3(-3.5f,1.65f+n*.14f,-.88f),new Vector3(.1f,.057f,.1f),dark,PrimitiveType.Cylinder);
                lamps[n]=lamp.GetComponent<Renderer>();
            }
            Part("Gantry_Leg_Main","Tower lamp post",new Vector3(-3.5f,1.14f,-.88f),new Vector3(.035f,.92f,.035f),dark);
            Label("01  INSPECT",new Vector3(-1.8f,.012f,-1.08f));
            Label("02  LIFT",new Vector3(.6f,.012f,-1.15f));
            Label("OK  >",new Vector3(3.25f,.012f,-.95f));
            cameraView=new GameObject("Main Camera").AddComponent<Camera>();
            cameraView.tag="MainCamera";
            cameraView.clearFlags=CameraClearFlags.SolidColor;
            cameraView.backgroundColor=new Color(.88f,.92f,.89f);
            cameraView.fieldOfView=39;
            cameraView.nearClipPlane=.1f; cameraView.farClipPlane=80;
        }

        public void SetCamera(string preset)
        {
            if(preset=="belt") { lookAt=new Vector3(-.8f,1,0); yaw=-10; pitch=48; distance=8.5f; }
            else if(preset=="sorting") { lookAt=new Vector3(.6f,1.5f,1.25f); yaw=-48; pitch=26; distance=6.5f; }
            else { lookAt=new Vector3(0,1,.6f); yaw=-30; pitch=36; distance=11.8f; }
        }

        private void LateUpdate()
        {
            if(model==null || cameraView==null) return;
            if(Input.GetMouseButton(0)) { yaw+=Input.GetAxis("Mouse X")*3; pitch=Mathf.Clamp(pitch-Input.GetAxis("Mouse Y")*2,12,75); }
            distance=Mathf.Clamp(distance-Input.mouseScrollDelta.y*.5f,4,17);
            cameraView.transform.position=lookAt+Quaternion.Euler(pitch,yaw,0)*new Vector3(0,0,-distance);
            cameraView.transform.LookAt(lookAt);
            var i=model.I;
            stopper.position=new Vector3(.6f,.9f+.18f*i.stopper,0);
            divider.position=new Vector3(-2.8f,.9f+.18f*i.divider,0);
            lifter.position=new Vector3(.6f,.98f+.25f*i.lift,0);
            carrier.gameObject.SetActive(i.carrier_present);
            carrier.position=new Vector3(i.carrier_x,1.045f+(i.stop_carrier ? .25f*i.lift : 0),0);
            float a1=i.axis1*1.25f, a2=i.axis2*1.25f;
            secondCylinder.position=new Vector3(.6f,2.45f,a1+.3f);
            piston1.position=new Vector3(.6f,2.7f,a1*.5f);
            piston2.position=new Vector3(.6f,2.45f,a1+a2*.5f);
            // Keep geometry thickness fixed; only exposed piston length changes.
            var p1=piston1.localScale; p1.z=Mathf.Max(.02f,a1)/.1f*piston1Base(); piston1.localScale=p1;
            var p2=piston2.localScale; p2.z=Mathf.Max(.02f,a2)/.1f*piston2Base(); piston2.localScale=p2;
            tool.position=new Vector3(.6f,2.03f-.48f*i.hoist,a1+a2);
            foreach(Transform child in tool)
            {
                if(child.name=="Jaw left") child.position=tool.position+new Vector3(-.15f+.09f*i.grip,-.25f,0);
                if(child.name=="Jaw right") child.position=tool.position+new Vector3(.15f-.09f*i.grip,-.25f,0);
            }
            for(int n=0;n<beltMarks.Count;n++) beltMarks[n].position=new Vector3(Mathf.Repeat(n*.35f+model.BeltTravel,7.7f)-3.85f,1.001f,0);
            var live=new HashSet<string>();
            int bin1=0,bin2=0;
            foreach(var record in model.Materials)
            {
                live.Add(record.id);
                if(!materialObjects.TryGetValue(record.id,out var obj))
                {
                    obj=Surface("Lid "+record.id,Vector3.zero,new Vector3(.30f,.025f,.30f),record.yellow?yellow:blue,PrimitiveType.Cylinder);
                    var marker=Surface("Direction",Vector3.zero,new Vector3(.17f,.006f,.035f),white);
                    marker.SetParent(obj,true);
                    materialObjects[record.id]=obj;
                }
                if(record.destination==0) obj.position=carrier.position+new Vector3(0,.075f,0);
                else if(record.destination==-1) obj.position=tool.position+new Vector3(0,-.20f,0);
                else
                {
                    int count=record.destination==1?bin1++:bin2++;
                    obj.position=new Vector3(.6f+(count%3-1)*.21f,1.235f+((count/3)%3)*.055f,record.destination*1.25f);
                }
                obj.rotation=Quaternion.Euler(0,record.reverse?180:0,0);
                obj.GetChild(0).position=obj.position+new Vector3(record.reverse?-.04f:.04f,.029f,0);
            }
            var remove=new List<string>();
            foreach(var pair in materialObjects) if(!live.Contains(pair.Key)){Destroy(pair.Value.gameObject);remove.Add(pair.Key);}
            foreach(var key in remove)materialObjects.Remove(key);
            int status=i.estop?3:model.Command.status;
            if(i.communication_hold && status==1)status=2;
            if(status!=previousStatus){previousStatus=status;lampPhase=Time.unscaledTime;}
            bool flash=(Time.unscaledTime-lampPhase)%2<1;
            lamps[0].sharedMaterial=status==1?teal:dark;
            lamps[1].sharedMaterial=status==0||(status==2&&flash)?yellow:dark;
            lamps[2].sharedMaterial=status==3&&flash?red:dark;
        }

        private float initialPiston1=-1,initialPiston2=-1;
        private float piston1Base(){if(initialPiston1<0)initialPiston1=piston1.localScale.z;return initialPiston1;}
        private float piston2Base(){if(initialPiston2<0)initialPiston2=piston2.localScale.z;return initialPiston2;}
    }
}
