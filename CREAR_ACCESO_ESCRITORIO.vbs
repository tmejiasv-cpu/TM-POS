Option Explicit
Dim fso, shell, folder, desktop, shortcut, exePath, launcherPath, iconPath
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

folder = fso.GetParentFolderName(WScript.ScriptFullName)
desktop = shell.SpecialFolders("Desktop")
exePath = folder & "\Tienda Mejia POS.exe"
launcherPath = folder & "\INICIAR_TIENDA_MEJIA.vbs"
iconPath = folder & "\assets\tienda_mejia.ico"

Set shortcut = shell.CreateShortcut(desktop & "\Tienda Mejia POS.lnk")

If fso.FileExists(exePath) Then
    shortcut.TargetPath = exePath
Else
    shortcut.TargetPath = "wscript.exe"
    shortcut.Arguments = """" & launcherPath & """"
End If

shortcut.WorkingDirectory = folder
shortcut.Description = "Tienda Mejia POS"
If fso.FileExists(iconPath) Then shortcut.IconLocation = iconPath
shortcut.Save

MsgBox "Acceso directo creado en el escritorio: Tienda Mejia POS", 64, "Tienda Mejia POS"
