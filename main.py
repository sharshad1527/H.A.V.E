import sys
import platform
from ui.main_gui import main

# --- Windows Taskbar Icon Fix ---
if platform.system() == "Windows":
    try:
        import ctypes
        myappid = 'harshad.have.editor.v1' # Unique identifier for our app
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass # Fail silently if ctypes isn't available

if __name__ == "__main__":
    main()
