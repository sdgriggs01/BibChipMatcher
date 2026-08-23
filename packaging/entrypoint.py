"""PyInstaller entry point. Kept separate from gui.py's own
`if __name__ == "__main__"` block so PyInstaller's import analysis has an
unambiguous, minimal script to start from."""

from gui import main

if __name__ == "__main__":
    main()
