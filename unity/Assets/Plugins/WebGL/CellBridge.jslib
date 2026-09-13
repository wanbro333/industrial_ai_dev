mergeInto(LibraryManager.library, {
  CellBind: function(name) { window.cellBridge.bind(UTF8ToString(name)); },
  CellTelemetry: function(json, epoch) { window.cellBridge.telemetry(UTF8ToString(json), UTF8ToString(epoch)); },
  CellUiEvent: function(json) { window.cellBridge.sendEvent(UTF8ToString(json)); },
  CellAck: function(json) { window.cellBridge.ack(UTF8ToString(json)); }
});
