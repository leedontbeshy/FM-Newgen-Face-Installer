import customtkinter as ctk


def confirm(parent, message: str, action: str, *, destructive=False) -> bool:
    """Cancel is the default; closing the window is also cancellation."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title(
        "Confirm removal"
        if destructive
        else "Fix newgen mapping"
        if action == "Fix Mapping"
        else "Replace face"
    )
    dialog.geometry("480x245")
    dialog.resizable(False, False)
    dialog.transient(parent)
    answer = False

    def finish(accepted=False):
        nonlocal answer
        answer = accepted
        dialog.grab_release()
        dialog.destroy()

    ctk.CTkLabel(dialog, text=message, wraplength=422, justify="left", font=("Segoe UI", 14)).pack(
        fill="x", padx=28, pady=(28, 20)
    )
    buttons = ctk.CTkFrame(dialog, fg_color="transparent")
    buttons.pack(side="bottom", fill="x", padx=28, pady=24)
    cancel = ctk.CTkButton(buttons, text="Cancel", fg_color="#35434a", hover_color="#42545c", command=finish)
    cancel.pack(side="left")
    ctk.CTkButton(
        buttons,
        text=action,
        fg_color="#a83a43" if destructive else "#167a62",
        hover_color="#892f38" if destructive else "#12634f",
        command=lambda: finish(True),
    ).pack(side="right")
    dialog.protocol("WM_DELETE_WINDOW", finish)
    dialog.bind("<Escape>", lambda event: finish())
    dialog.after(80, lambda: (dialog.grab_set(), cancel.focus_set()))
    parent.wait_window(dialog)
    return answer
