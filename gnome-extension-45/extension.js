/*
 * GNOME 45+ build of the Narenj helper (ES modules). Same behaviour as the GNOME 42-44
 * extension in ../gnome-extension: keeps the wheel above other windows on every
 * workspace and reports the modifier keys held while a file is dragged in.
 */
import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const APP_ID = 'ir.narenj.Narenj';
const IFACE = `
<node>
  <interface name="ir.narenj.Shell">
    <method name="GetModifiers">
      <arg type="u" direction="out" name="modifiers"/>
    </method>
  </interface>
</node>`;

export default class NarenjExtension extends Extension {
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
