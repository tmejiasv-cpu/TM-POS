Option Explicit
Dim fso, shell, folder, pyw, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
folder = fso.GetParentFolderName(WScript.ScriptFullName)

pyw = ""
On Error Resume Next
pyw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe")
If Not fso.FileExists(pyw) Then pyw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe")
If Not fso.FileExists(pyw) Then pyw = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe")
If Not fso.FileExists(pyw) Then pyw = "pythonw.exe"
On Error GoTo 0

cmd = """" & pyw & """ """ & folder & "\main.py"""
shell.Run cmd, 0, False
