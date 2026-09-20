import customtkinter as ctk


class PreviewLabel(ctk.CTkLabel):
    """Clear Tk's image reference before an old preview can be released."""

    def _update_image(self):
        # CTkLabel 6.0 does nothing for image=None, leaving the Tcl label bound
        # to a PhotoImage which may subsequently be garbage-collected.
        if self._image is None:
            self._label.configure(image="")
        else:
            super()._update_image()
