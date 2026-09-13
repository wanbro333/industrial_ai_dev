using System;
using System.Runtime.InteropServices;
using UnityEngine;

namespace IndustrialCell
{
    [Serializable] public class OutputEnvelope { public string id, epoch; public Outputs data; }
    [Serializable] public class UiAction { public string action, recipe; public bool value; }
    [Serializable] public class CommandAck { public string command_id, outcome; }

    public sealed class MqttBridge : MonoBehaviour
    {
        public DeviceModel Model { get; private set; }
        private float nextPublish;
        private string previousSensors = "";
#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] private static extern void CellBind(string name);
        [DllImport("__Internal")] private static extern void CellTelemetry(string json, string epoch);
        [DllImport("__Internal")] private static extern void CellUiEvent(string json);
        [DllImport("__Internal")] private static extern void CellAck(string json);
#endif
        private void Awake() { Model = new DeviceModel(); }
        private void Start()
        {
            Application.targetFrameRate = 60;
            Application.runInBackground = true;
#if UNITY_WEBGL && !UNITY_EDITOR
            CellBind(gameObject.name);
#else
            Debug.Log("Build WebGL to connect the Python controller through MQTT.js. Editor preview shows equipment only.");
#endif
        }
        private void Update()
        {
            Model.Tick(Time.unscaledDeltaTime, Time.realtimeSinceStartupAsDouble);
            string sensors = Model.I.detect_carrier + ":" + Model.I.stop_carrier + ":" + Model.I.holding
                + ":" + Model.I.communication_hold + ":" + Model.I.device_fault + ":" + Model.I.feed_ack;
            if (Time.unscaledTime >= nextPublish || previousSensors != sensors)
            {
                previousSensors = sensors;
                PublishInputs();
            }
        }
        private void PublishInputs()
        {
            nextPublish = Time.unscaledTime + .2f;
#if UNITY_WEBGL && !UNITY_EDITOR
            CellTelemetry(JsonUtility.ToJson(Model.I), Model.Epoch);
#endif
        }
        public void OnOutputs(string raw)
        {
            try
            {
                var envelope = JsonUtility.FromJson<OutputEnvelope>(raw);
                bool accepted = envelope != null && envelope.epoch == Model.Epoch
                    && Model.Apply(envelope.data, Time.realtimeSinceStartupAsDouble);
#if UNITY_WEBGL && !UNITY_EDITOR
                CellAck(JsonUtility.ToJson(new CommandAck { command_id = envelope == null ? "" : envelope.id,
                    outcome = accepted ? "applied" : "rejected" }));
#endif
                if (envelope != null && envelope.epoch != Model.Epoch) PublishInputs();
            }
            catch (Exception exception) { Debug.LogWarning("Rejected output: " + exception.Message); }
        }
        public void OnConnection(string state) { Model.SetConnection(state == "connected"); PublishInputs(); }
        public void OnVisibility(string state) { Model.SetVisible(state == "visible"); PublishInputs(); }
        public void OnControllerChanged(string _) { Model.Hold(); }
        public void OnStartToken(string token) { Model.AuthorizeStart(token); }
        public void OnUiEvent(string raw)
        {
            var action = JsonUtility.FromJson<UiAction>(raw);
            if (action == null) return;
            switch (action.action)
            {
                case "estop": Model.ResetScene(true); break;
                case "release": if (Model.I.estop) Model.ResetScene(false, true); break;
                case "reset": if (!Model.ResetScene(false)) return; break;
                case "stop": Model.Hold(); break;
                case "mode": Model.SetAutomatic(action.value); break;
                case "clear_counts": Model.ClearCounters(); break;
                case "jam": Model.JamAxis = action.recipe; break;
                case "camera": GetComponent<CellScene>().SetCamera(action.recipe); return;
            }
            PublishInputs(); // New epoch / selector / emergency reaches the controller before button events.
#if UNITY_WEBGL && !UNITY_EDITOR
            CellUiEvent(raw);
#endif
        }
    }
}
