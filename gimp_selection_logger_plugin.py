#!/usr/bin/env python3
"""GIMP plugin to log current selection's position and size in a text file in
XWindow geometry format, i.e. wxh+w+y

Useful to load a photo or the screenshot of a video from a camera and manually
tag stuck pixels for removal with ffmpeg's delogo filter for example

Install this script in its own directory in GIMP's plug-ins directory, with the
directory name equivalent to the stem of the script's name e.g.

  ~/.config/GIMP/3.0/plug-ins/gimp_selection_logger_plugin/

Then make the script executable:

  chmod +x gimp_selection_logger_plugin.py

Finally, restart GIMP.

It installs two new menu items in Tools/Selection Tools:

  - Log the current selection
  - Delete the selection log file"
"""

### Parameters
selection_log_file = "~/gimp_selections.log"
procedures_menu_path = "<Image>/Tools/Selection Tools"



### Modules
import os
import sys
from datetime import datetime

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GLib, Gtk, GObject



### Classes
class GimpSelectionLogger(Gimp.PlugIn):

  def __init__(self):
    """__init__ method
    """

    # Resolve ~ in the log file path and find the absolute path
    self.selection_log_file_abspath = os.path.abspath(
					os.path.expanduser(selection_log_file))



  def do_query_procedures(self):
    """GIMP procedure names registration callback
    """


    return ["log-current-selection",
		"delete-selection-log"]



  def do_create_procedure(self, name):
    """Procedures initialization callback
    """

    if name == "log-current-selection":

      procedure = Gimp.ImageProcedure.new(self,
						name,
						Gimp.PDBProcType.PLUGIN,
						self.log_current_selection,
						None)

      procedure.set_image_types("*")
      procedure.set_menu_label("Log the current selection")
      procedure.add_menu_path(procedures_menu_path)
      procedure.set_documentation(
		"Log the current selection's coordinates and size to {}".
			format(selection_log_file),
		"Writes the current selection's X, Y, W and H as WxH+X+Y to {}".
			format(selection_log_file),
		name)
      procedure.set_attribution("Giraut", "Giraut", "2026")

    elif name == "delete-selection-log":

      procedure = Gimp.Procedure.new(self,
					name,
					Gimp.PDBProcType.PLUGIN,
					self.delete_selection_log,
					None)

      procedure.add_enum_argument("run-mode",
					"Run mode",
					"Run mode",
					Gimp.RunMode.__gtype__,
					Gimp.RunMode.INTERACTIVE,
					GObject.ParamFlags.READWRITE)

      procedure.set_menu_label("Delete the selection log file")
      procedure.add_menu_path(procedures_menu_path)
      procedure.set_documentation(
		"Delete the current selection log file {}".
			format(selection_log_file),
		None,
		name)
      procedure.set_attribution("Giraut", "Giraut", "2026")

    return procedure



  def do_set_i18n(self, procedure):
    """Localization config callback: disable localization
    """

    return False, None, None



  def log_current_selection(self, procedure, runmode, image,
					drawables, config, rundata):
    """Execution callback for the procedure to log the current selection
    """

    try:

      success, has_selection, x1, y1, x2, y2 = Gimp.Selection.bounds(image)

      if not success:
        raise RuntimeError("could not get selection bounds")

      if not has_selection:
        Gimp.message("No active selection to log")
        return procedure.new_return_values(
				Gimp.PDBStatusType.EXECUTION_ERROR,
				GLib.Error("no active selection to log"))

      log_line = "{}x{}+{}+{}".format(x2 - x1, y2 - y1, x1, y1)

      with open(self.selection_log_file_abspath, "a") as f:
        print(log_line, file = f)

      Gimp.message("Active selection logged as {} in {}".
			format(log_line, selection_log_file))

      return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

    except Exception as e:

      Gimp.message("Could not log active selection: {}".format(e))

      return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
						GLib.Error(str(e)))



  def delete_selection_log(self, procedure, config, rundata):
    """Execution callback for the procedure to delete the selection log file
    """

    # Pop a confirmation dialog
    delete_confirm_dialog = Gtk.MessageDialog(
					transient_for = None,
					modal = True,
					message_type = Gtk.MessageType.WARNING,
					buttons = Gtk.ButtonsType.NONE,
					text = "Delete the selection log file?")
    delete_confirm_dialog.format_secondary_text(selection_log_file)
    delete_confirm_dialog.add_button("_Cancel", Gtk.ResponseType.CANCEL)
    delete_confirm_dialog.add_button("_Delete", Gtk.ResponseType.ACCEPT)

    response = delete_confirm_dialog.run()
    delete_confirm_dialog.destroy()

    if response == Gtk.ResponseType.ACCEPT:

      try:

        if os.path.exists(self.selection_log_file_abspath):
          os.unlink(self.selection_log_file_abspath)

        Gimp.message("Selection log file {} deleted".format(selection_log_file))

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)

      except Exception as e:

        Gimp.message("Could not delete selection log: {}".format(e))

        return procedure.new_return_values(Gimp.PDBStatusType.EXECUTION_ERROR,
						GLib.Error(str(e)))

    Gimp.message("Cancelled".format(selection_log_file))

    return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, None)



### Main program
if __name__ == "__main__":
  Gimp.main(GimpSelectionLogger.__gtype__, sys.argv)
