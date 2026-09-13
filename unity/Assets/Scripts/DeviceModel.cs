using System;
using System.Collections.Generic;

namespace IndustrialCell
{
    [Serializable]
    public class Outputs
    {
        public int status;
        public string step = "HOME", fault = "", note = "", feed_id = "", feed_recipe = "";
        public string run_token = "", ui_ack = "", result = "", material_id = "";
        public bool ready, motion_allowed, motor, auto_feed;
        public int queued;
        public float divider, stopper, lift, axis1, axis2, hoist, grip, step_elapsed;
    }

    [Serializable]
    public class Inputs
    {
        public bool estop, visible = true, automatic = true, communication_hold = true;
        public bool carrier_present, material_present, divider_carrier, detect_carrier, detect_material, stop_carrier, stop_material;
        public bool color_yellow, direction_reverse, holding;
        public float divider = 1, stopper = 1, lift, axis1, axis2, hoist, grip, carrier_x = -3.7f;
        public string carrier_id = "", material_id = "", feed_ack = "", device_fault = "", run_token_seen = "";
        public int bin1_count, bin2_count, ok_count, empty_count;
    }

    public class MaterialRecord
    {
        public string id, recipe;
        public bool yellow, reverse;
        public int destination; // 0: on carrier, -1: gripped, 1/2: bin. Not a sorting decision.
    }

    /// <summary>Deterministic virtual equipment. No production steps or color-based routing here.</summary>
    public sealed class DeviceModel
    {
        public readonly Inputs I = new Inputs();
        public Outputs Command = new Outputs();
        public readonly List<MaterialRecord> Materials = new List<MaterialRecord>();
        public string Epoch { get; private set; } = Guid.NewGuid().ToString("N");
        public bool Connected { get; private set; }
        public float BeltTravel { get; private set; }
        public string JamAxis = ""; // Deliberate training fault injection.
        public string BlockedRunToken = "";
        public string AuthorizedStartToken { get; private set; } = "";
        public double LastCommandAt { get; private set; } = double.NegativeInfinity;
        private string lastFeed = "";
        private bool retiredCarrierHadMaterial;
        private readonly HashSet<string> fed = new HashSet<string>();

        public void Hold()
        {
            I.communication_hold = true;
            BlockedRunToken = Command.run_token ?? "";
            AuthorizedStartToken = "";
        }

        public void AuthorizeStart(string token)
        {
            if (I.visible && I.automatic && !I.estop) AuthorizedStartToken = token;
        }

        public void SetConnection(bool connected)
        {
            Connected = connected;
            if (!connected) Hold();
        }

        public void SetVisible(bool visible)
        {
            I.visible = visible;
            if (!visible) Hold();
        }

        public void SetAutomatic(bool automatic)
        {
            I.automatic = automatic;
            if (!automatic) Hold();
        }

        public bool ResetScene(bool emergency, bool release = false)
        {
            if (!emergency && !release && (I.estop || Command.status == 1)) return false;
            I.estop = emergency;
            Epoch = Guid.NewGuid().ToString("N");
            Hold();
            Command = new Outputs();
            Command.status = emergency ? 3 : 0;
            I.carrier_present = I.material_present = I.holding = false;
            I.carrier_id = I.material_id = I.feed_ack = "";
            Materials.Clear(); // Includes held and previously deposited virtual material.
            fed.Clear();
            lastFeed = "";
            I.device_fault = "";
            LastCommandAt = double.NegativeInfinity;
            UpdateSensors();
            return true;
        }

        public void ClearCounters()
        {
            if (Command.status == 0)
                I.bin1_count = I.bin2_count = I.ok_count = I.empty_count = 0;
        }

        public bool Apply(Outputs next, double now)
        {
            if (next == null || next.status < 0 || next.status > 3) return false;
            float[] values = { next.divider, next.stopper, next.lift, next.axis1, next.axis2, next.hoist, next.grip };
            foreach (float value in values)
                if (float.IsNaN(value) || float.IsInfinity(value) || value < 0 || value > 1) return false;
            // A local latch cannot be cleared by a remote status field.
            if (I.estop && next.status != 3) return false;
            if (next.status == 3 && !I.estop)
            {
                ResetScene(true);
                return false; // Publish a new epoch; previous-epoch commands can no longer apply.
            }
            if (next.status == 1 && I.communication_hold)
            {
                if (string.IsNullOrEmpty(next.run_token) || next.run_token != AuthorizedStartToken
                    || next.run_token == BlockedRunToken || !I.visible || !I.automatic)
                    return false;
                I.communication_hold = false;
            }
            Command = next;
            I.run_token_seen = next.run_token;
            LastCommandAt = now;
            return true;
        }

        public void Tick(float delta, double now)
        {
            if (!Connected || now - LastCommandAt > 3 || !I.visible) Hold();
            float dt = Math.Min(Math.Max(delta, 0), .05f); // No hidden-tab catch-up.
            bool initialize = Command.status == 0 && !I.estop;
            bool run = Command.status == 1 && !I.communication_hold && I.automatic;
            bool enabled = Connected && I.visible && !I.estop && now - LastCommandAt <= 3
                           && Command.motion_allowed && (initialize || run) && string.IsNullOrEmpty(I.device_fault);
            if (!enabled) { UpdateSensors(); return; }

            // Equipment-level interlocks: horizontal moves require raised hoist.
            bool horizontalWanted = Math.Abs(Command.axis1 - I.axis1) > .015f || Math.Abs(Command.axis2 - I.axis2) > .015f;
            if (horizontalWanted && I.hoist > .015f)
            {
                if (initialize) I.hoist = Move("hoist", I.hoist, 0, dt);
                else { I.device_fault = "HORIZONTAL_WITH_HOIST_DOWN"; Hold(); }
                UpdateSensors(); return;
            }
            I.divider = Move("divider", I.divider, Command.divider, dt);
            I.stopper = Move("stopper", I.stopper, Command.stopper, dt);
            I.lift = Move("lift", I.lift, Command.lift, dt);
            I.axis1 = Move("axis1", I.axis1, Command.axis1, dt);
            I.axis2 = Move("axis2", I.axis2, Command.axis2, dt);
            I.hoist = Move("hoist", I.hoist, Command.hoist, dt);
            I.grip = Move("grip", I.grip, Command.grip, dt);

            if (run && !string.IsNullOrEmpty(Command.feed_id) && !fed.Contains(Command.feed_id) && !I.carrier_present)
                Feed(Command.feed_id, Command.feed_recipe);
            MaterialRecord active = Materials.Find(m => m.id == I.material_id);
            if (active != null && active.destination == 0 && I.grip >= .985f && I.hoist >= .985f
                && I.axis1 <= .015f && I.axis2 <= .015f && I.lift >= .985f && I.stop_carrier)
            {
                active.destination = -1;
                I.holding = true;
            }
            if (I.holding && I.grip <= .015f)
            {
                if (I.hoist >= .985f && I.axis1 >= .985f && (I.axis2 <= .015f || I.axis2 >= .985f))
                {
                    // Destination is detected from actual gripper position, never color/orientation.
                    int destination = I.axis2 >= .985f ? 2 : 1;
                    active.destination = destination;
                    if (destination == 1) I.bin1_count++; else I.bin2_count++;
                    I.holding = false;
                    I.material_present = false;
                }
                else { I.device_fault = "RELEASE_OUTSIDE_BIN"; Hold(); }
            }
            if (run && Command.motor && I.lift <= .015f)
            {
                BeltTravel += dt * .85f;
                if (I.carrier_present)
                {
                    float next = I.carrier_x + .85f * dt;
                    if (I.divider > .1f && I.carrier_x <= -2.8f) next = Math.Min(next, -2.8f);
                    if (I.stopper > .1f && I.carrier_x <= .6f) next = Math.Min(next, .6f);
                    I.carrier_x = next;
                    if (next > 3.9f)
                    {
                        if (active != null && active.destination == 0) { I.ok_count++; Materials.Remove(active); }
                        else if (!retiredCarrierHadMaterial) I.empty_count++;
                        I.carrier_present = I.material_present = false;
                        I.carrier_id = I.material_id = "";
                    }
                }
            }
            // Bound rendered historical material; counters remain cumulative until explicitly cleared.
            while (Materials.Count > 18)
            {
                int old = Materials.FindIndex(m => m.destination > 0);
                if (old < 0) break;
                Materials.RemoveAt(old);
            }
            UpdateSensors();
        }

        private float Move(string name, float value, float target, float dt)
        {
            if (JamAxis == name) return value;
            float speed = name == "axis1" || name == "axis2" ? .75f : 1.8f;
            return value < target ? Math.Min(target, value + speed * dt) : Math.Max(target, value - speed * dt);
        }

        private void Feed(string id, string recipe)
        {
            if (recipe != "blue_forward" && recipe != "blue_reverse" && recipe != "yellow_forward"
                && recipe != "yellow_reverse" && recipe != "empty") return;
            if (fed.Count >= 4096) { I.device_fault = "SESSION_CAPACITY_RESET_REQUIRED"; Hold(); return; }
            fed.Add(id);
            lastFeed = I.feed_ack = id;
            I.carrier_id = id;
            I.carrier_present = true;
            I.carrier_x = -3.7f;
            retiredCarrierHadMaterial = recipe != "empty";
            I.material_present = retiredCarrierHadMaterial;
            if (I.material_present)
            {
                I.material_id = id + "-lid";
                Materials.Add(new MaterialRecord { id = I.material_id, recipe = recipe,
                    yellow = recipe.StartsWith("yellow"), reverse = recipe.EndsWith("reverse") });
            }
        }

        private void UpdateSensors()
        {
            I.divider_carrier = I.carrier_present && System.Math.Abs(I.carrier_x + 2.8f) <= .25f;
            I.detect_carrier = I.carrier_present && Math.Abs(I.carrier_x + 1.8f) <= .28f;
            I.stop_carrier = I.carrier_present && Math.Abs(I.carrier_x - .6f) <= .035f;
            MaterialRecord active = Materials.Find(m => m.id == I.material_id && m.destination == 0);
            I.detect_material = I.detect_carrier && active != null;
            I.stop_material = I.stop_carrier && active != null;
            I.color_yellow = I.detect_material && active.yellow;
            I.direction_reverse = I.detect_material && active.reverse;
        }
    }
}
