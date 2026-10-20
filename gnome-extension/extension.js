/*
 * Helps the Narenj wheel on Wayland, where apps cannot do these themselves:
 * keeps its window above the others on every workspace, and tells it which
 * modifier keys are held while a file is dragged in from another app.
 */
const { Gio, Meta } = imports.gi;

const APP_ID = 'ir.narenj.Narenj';
const IFACE = `
<node>
  <interface name="ir.narenj.Shell">
    <method name="GetModifiers">
      <arg type="u" direction="out" name="modifiers"/>
    </method>
  </interface>
</node>`;

class Extension {
    enable() {
        this._createdId = global.display.connect('window-created', (_display, win) => this._watch(win));
        global.get_window_actors().forEach(actor => this._pin(actor.meta_window));
        this._dbus = Gio.DBusExportedObject.wrapJSObject(IFACE, this);
        this._dbus.export(Gio.DBus.session, '/ir/narenj/Shell');
    }

    disable() {
        this._dbus.unexport();
        this._dbus = null;
        global.display.disconnect(this._createdId);
        this._createdId = 0;
        global.get_window_actors()
            .map(actor => actor.meta_window)
            .filter(win => this._isWheel(win))
            .forEach(win => {
                win.unmake_above();
                win.unstick();
            });
    }

    GetModifiers() {
        const [, , modifiers] = global.get_pointer();
        return modifiers;
    }

    _isWheel(win) {
        return win.get_wm_class() === APP_ID && win.get_window_type() === Meta.WindowType.NORMAL;
    }

    _watch(win) {
        // the Wayland app_id can arrive just after the window is created
        if (this._pin(win))
            return;
        const id = win.connect('notify::wm-class', () => {
            if (this._pin(win))
                win.disconnect(id);
        });
    }

    _pin(win) {
        if (!this._isWheel(win))
            return false;
        win.make_above();
        win.stick();
        return true;
    }
}

function init() {
    return new Extension();
}
