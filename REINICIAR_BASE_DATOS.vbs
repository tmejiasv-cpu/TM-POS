Option Explicit
Dim fso, shell, folder, db, backupFolder, stamp, backupFile, r1, r2
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

folder = fso.GetParentFolderName(WScript.ScriptFullName)
db = folder & "\tienda_mejia.db"
backupFolder = folder & "\backups"

If Not fso.FileExists(db) Then
    MsgBox "No existe tienda_mejia.db. La base ya está vacía o todavía no ha sido creada.", 64, "Reiniciar base"
    WScript.Quit
End If

r1 = MsgBox( _
    "IMPORTANTE:" & vbCrLf & vbCrLf & _
    "Cierre Tienda Mejia POS antes de continuar." & vbCrLf & _
    "Este proceso reiniciará ventas, compras, productos, inventario, caja, gastos y usuarios." & vbCrLf & vbCrLf & _
    "Se creará una copia de respaldo antes de borrar la base actual." & vbCrLf & vbCrLf & _
    "¿Desea continuar?", _
    52, "Reiniciar base de datos")

If r1 <> 6 Then WScript.Quit

r2 = MsgBox( _
    "CONFIRMACIÓN FINAL" & vbCrLf & vbCrLf & _
    "¿Está completamente seguro de dejar la base de datos en cero?", _
    52, "Confirmación final")

If r2 <> 6 Then WScript.Quit

If Not fso.FolderExists(backupFolder) Then fso.CreateFolder(backupFolder)

stamp = Year(Now) & Right("0" & Month(Now),2) & Right("0" & Day(Now),2) & "_" & _
        Right("0" & Hour(Now),2) & Right("0" & Minute(Now),2) & Right("0" & Second(Now),2)

backupFile = backupFolder & "\tienda_mejia_" & stamp & ".db"

On Error Resume Next
fso.CopyFile db, backupFile, True
If Err.Number <> 0 Then
    MsgBox "No se pudo crear el respaldo." & vbCrLf & _
           "Asegúrese de que la aplicación esté cerrada." & vbCrLf & vbCrLf & _
           Err.Description, 16, "Error"
    WScript.Quit
End If

Err.Clear
fso.DeleteFile db, True
If Err.Number <> 0 Then
    MsgBox "Se creó el respaldo, pero no fue posible borrar la base actual." & vbCrLf & _
           "Cierre la aplicación e inténtelo nuevamente." & vbCrLf & vbCrLf & _
           "Respaldo: " & backupFile, 16, "Error"
    WScript.Quit
End If
On Error GoTo 0

MsgBox _
    "Base de datos reiniciada correctamente." & vbCrLf & vbCrLf & _
    "Respaldo creado en:" & vbCrLf & backupFile & vbCrLf & vbCrLf & _
    "Al abrir nuevamente Tienda Mejia POS se creará una base nueva." & vbCrLf & _
    "Usuario inicial: admin" & vbCrLf & _
    "Contraseña inicial: admin123", _
    64, "Proceso completado"
