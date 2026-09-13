using System;
using System.Text.Json;
using IndustrialCell;

class Program
{
    static void Main()
    {
        var model = new DeviceModel();
        model.SetConnection(true);
        var options = new JsonSerializerOptions { IncludeFields = true };
        string line;
        while ((line = Console.ReadLine()) != null)
        {
            using (var doc = JsonDocument.Parse(line))
            {
                var root = doc.RootElement;
                if (root.TryGetProperty("action", out var action))
                {
                    switch (action.GetString())
                    {
                        case "estop": model.ResetScene(true); break;
                        case "release": model.ResetScene(false, true); break;
                        case "reset": model.ResetScene(false); break;
                        case "hide": model.SetVisible(false); break;
                        case "show": model.SetVisible(true); break;
                        case "disconnect": model.SetConnection(false); break;
                        case "connect": model.SetConnection(true); break;
                        case "hold": model.Hold(); break;
                    }
                }
                if (root.TryGetProperty("jam", out var jam)) model.JamAxis = jam.GetString();
                if (root.TryGetProperty("authorize", out var authorize)) model.AuthorizeStart(authorize.GetString());
                double time = root.TryGetProperty("t", out var t) ? t.GetDouble() : 0;
                if (root.TryGetProperty("outputs", out var outputs))
                    model.Apply(JsonSerializer.Deserialize<Outputs>(outputs.GetRawText(), options), time);
                model.Tick(root.TryGetProperty("dt", out var dt) ? dt.GetSingle() : 0, time);
                Console.WriteLine(JsonSerializer.Serialize(new { epoch = model.Epoch, inputs = model.I,
                    material_count = model.Materials.Count }, options));
            }
        }
    }
}
