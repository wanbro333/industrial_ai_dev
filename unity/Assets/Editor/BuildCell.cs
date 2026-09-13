using System;
using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using IndustrialCell;

public static class BuildCell
{
    [MenuItem("Industrial Cell/Create or rebuild scene")]
    public static void CreateScene()
    {
        EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var cell = new GameObject("Cell");
        cell.AddComponent<MqttBridge>();
        cell.AddComponent<CellScene>();
        Directory.CreateDirectory("Assets/Resources/Materials");
        const string anchorPath = "Assets/Resources/Materials/RuntimeStandard.mat";
        if (AssetDatabase.LoadAssetAtPath<Material>(anchorPath) == null)
            AssetDatabase.CreateAsset(new Material(Shader.Find("Standard")), anchorPath);
        // A Resources material keeps the runtime-created equipment shader in player builds.
        Directory.CreateDirectory("Assets/Resources/Primitives");
        foreach (var shape in new[] { PrimitiveType.Cube, PrimitiveType.Cylinder })
        {
            var primitive = GameObject.CreatePrimitive(shape);
            UnityEngine.Object.DestroyImmediate(primitive.GetComponent<Collider>());
            primitive.GetComponent<Renderer>().sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>(anchorPath);
            PrefabUtility.SaveAsPrefabAsset(primitive, "Assets/Resources/Primitives/" + shape + ".prefab");
            UnityEngine.Object.DestroyImmediate(primitive);
        }
        Directory.CreateDirectory("Assets/Scenes");
        EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(), "Assets/Scenes/Cell.unity");
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene("Assets/Scenes/Cell.unity", true) };
        PlayerSettings.companyName = "Industrial AI Lab";
        PlayerSettings.productName = "Conveyor Cell";
        PlayerSettings.bundleVersion = "0.1.0";
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.runInBackground = true;
        PlayerSettings.WebGL.template = "PROJECT:Industrial";
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.initialMemorySize = 128;
        PlayerSettings.WebGL.maximumMemorySize = 1024;
        PlayerSettings.SetScriptingBackend(UnityEditor.Build.NamedBuildTarget.WebGL, ScriptingImplementation.IL2CPP);
        QualitySettings.antiAliasing = 2;
        QualitySettings.shadowDistance = 25;
        QualitySettings.shadows = ShadowQuality.All;
        AssetDatabase.SaveAssets();
    }

    [MenuItem("Industrial Cell/Build WebGL")]
    public static void WebGL()
    {
        CreateScene();
        string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../../web/dist"));
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
            scenes = new[] { "Assets/Scenes/Cell.unity" }, locationPathName = output,
            target = BuildTarget.WebGL, options = BuildOptions.None
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new Exception("WebGL build failed: " + report.summary.result);
        Debug.Log("CELL_WEBGL_BUILD_OK " + output);
    }
}
