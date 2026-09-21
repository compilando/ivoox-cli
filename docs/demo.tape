Output docs/demo.gif

Require ivx
Require mpv
Require python

Set Shell "bash"
Set Width 1200
Set Height 720
Set FontSize 20
Set TypingSpeed 45ms
Set Theme { "name": "Catppuccin Mocha", "black": "#45475a", "red": "#f38ba8", "green": "#a6e3a1", "yellow": "#f9e2af", "blue": "#89b4fa", "magenta": "#f5c2e7", "cyan": "#94e2d5", "white": "#bac2de", "brightBlack": "#585b70", "brightRed": "#f38ba8", "brightGreen": "#a6e3a1", "brightYellow": "#f9e2af", "brightBlue": "#89b4fa", "brightMagenta": "#f5c2e7", "brightCyan": "#94e2d5", "brightWhite": "#a6adc8", "background": "#1e1e2e", "foreground": "#cdd6f4", "selection": "#585b70", "cursor": "#f5e0dc" }

Env IVX_DIR ".demo/library"
Env IVX_CFG ".demo/config"

Hide
Type "python docs/demo_setup.py"
Enter
Sleep 1s
Show

Type "ivx tui --local"
Enter
Sleep 3s
Type "f"
Type@120ms "ciencia"
Sleep 2s
Enter
Sleep 1s
Tab
Enter
Sleep 4s
Type "q"
