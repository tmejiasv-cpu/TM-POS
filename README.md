
# Tienda Mejía POS — Prototipo funcional

Este proyecto es una primera versión de una aplicación de escritorio para Tienda Mejía.

## Funciones incluidas
- Inicio de sesión con roles Gerente y Empleado.
- El Gerente puede crear, modificar, activar/desactivar y eliminar usuarios/empleados, además de asignar jornada.
- Gerente y Empleado pueden registrar productos.
- Registro de compras y entradas de inventario.
- Control de inventario por lotes.
- Costo de venta con método FIFO/PEPS.
- Punto de venta.
- Inicio de caja y cierre con arqueo.
- Gastos solicitados por empleados.
- Los gastos quedan PENDIENTES y deben ser aprobados/rechazados por el Gerente.
- No permite cerrar la caja mientras existan gastos pendientes de autorización.
- Reporte básico de ventas, costo y utilidad bruta por empleado y fecha.
- Logo de Tienda Mejía integrado.

## Primer acceso
Usuario: admin
Contraseña: admin123

IMPORTANTE: cambie esta contraseña antes de usar el sistema en producción.

## Requisitos
- Windows 10/11
- Python 3.11 o superior
- Pillow

Instalación:
    pip install -r requirements.txt

Ejecución:
    python main.py

La base de datos `tienda_mejia.db` se crea automáticamente en la misma carpeta.

## Nota sobre utilidad
El sistema mantiene cada compra como un lote separado. Cuando se vende un producto, consume primero el inventario más antiguo (FIFO/PEPS), conservando el costo real de cada lote. Así la utilidad no depende de un único "costo actual".

## Próximas mejoras sugeridas
- Cambio de contraseña.
- Edición/desactivación de productos.
- Compras con varios productos en una sola factura.
- Venta mediante lector de código de barras.
- Ticket para impresora térmica.
- Arqueo por denominaciones.
- Entradas/retiros de caja independientes.
- Reportes PDF/Excel.
- Copias de seguridad automáticas.
- Historial/auditoría de acciones.
- Devoluciones y anulaciones con autorización del gerente.


## Gestión segura de empleados
- Un usuario sin movimientos históricos puede eliminarse definitivamente.
- Si un empleado ya tiene ventas, compras, gastos o sesiones de caja, el sistema no borra su registro histórico: lo desactiva.
- Un usuario desactivado ya no puede iniciar sesión.
- El gerente puede modificar nombre, usuario, jornada, rol, estado y restablecer contraseña.
- El sistema impide que el gerente elimine o desactive accidentalmente la cuenta con la que está conectado.


## Versión 1.2
- Corregido el formulario de productos: el botón Guardar ahora permanece accesible y el formulario tiene desplazamiento vertical.
- Edición de productos desde Inventario.
- Punto de venta mejorado para lector de código de barras (Enter agrega el producto).
- Se puede quitar un producto seleccionado del carrito.
- Pago en efectivo con monto recibido y cálculo automático del cambio.
- El monto recibido y el cambio se almacenan con la venta.
- Arqueo de caja por denominaciones de billetes y monedas.
- El desglose del arqueo se guarda junto con el cierre de caja.
- Resumen de caja con fondo inicial, efectivo, transferencias, gastos y efectivo esperado.


## Versión 1.3
- Código de producto automático: PRTM + año de 2 dígitos + correlativo de 4 dígitos. Ejemplo: PRTM260001.
- Búsqueda de productos por nombre en Inventario, Ventas y Compras.
- Catálogo acumulativo de categorías: al escribir una nueva categoría queda disponible para futuros productos.
- Compras con múltiples productos dentro de una misma factura/documento.
- Historial de movimientos de inventario.
- Registro de qué usuario hizo cada movimiento.
- Anulación de ventas desde el área de Gerente, con motivo y devolución de existencias.
- Las ventas anuladas dejan de contar en caja y reportes.
- Reporte detallado de cortes de caja y desglose de denominaciones.


## Versión 1.4
- Se reemplazó la navegación por pestañas por un menú lateral fijo.
- Todos los módulos principales quedan siempre visibles: Inicio, Ventas, Productos, Compras, Caja, Gastos y, para Gerente, Empleados y Reportes.
- La aplicación intenta abrir maximizada para aprovechar mejor la pantalla.
- Se reorganizó el Punto de Venta en dos filas para evitar que los botones queden fuera del área visible.
- El botón Agregar y los controles de búsqueda de ventas ahora caben mejor en resoluciones pequeñas o con escalado de Windows.


## Versión 1.4.1
- Corregida la ventana Registrar compra.
- El encabezado y el pie de la ventana ahora permanecen fijos.
- Solo la tabla central se expande o reduce con el tamaño de la ventana.
- Los botones Guardar compra, Cancelar y Quitar seleccionado permanecen siempre visibles.
- El total de la compra permanece visible en la parte inferior.
- Se añadió barra de desplazamiento vertical a la tabla.
- Enter en Cantidad o Costo unitario también agrega el producto.


## Versión 1.5
- Rediseño completo del Punto de Venta.
- Panel de carrito grande y panel de cobro fijo a la derecha.
- Total, efectivo recibido y cambio siempre visibles.
- Indicador visible de Caja Abierta / Caja Cerrada.
- Búsqueda de productos por nombre, código o categoría.
- Lectura por código de barras y código interno.
- Muestra existencia disponible del producto seleccionado.
- Botones +1, -1, Quitar y Vaciar venta.
- Contador de unidades en la venta.
- Atajos: F2 buscar, F4 cobrar y Delete quitar producto.
- Cobro por efectivo, transferencia u otro medio.
- El botón COBRAR VENTA permanece siempre visible.


## Versión 1.5
- Punto de venta rediseñado con dos áreas: carrito y panel fijo de cobro.
- El botón COBRAR permanece siempre visible.
- Total grande y visible en todo momento.
- Búsqueda simultánea por nombre, código interno y código de barras.
- Visualización del stock disponible antes de agregar.
- Botones +1, -1, Quitar y Vaciar venta para manejar el carrito.
- Cantidad total de artículos visible.
- Panel de pago con método, efectivo recibido y cambio.
- El efectivo recibido se desactiva automáticamente para transferencias u otros métodos.
- Mensaje de faltante cuando el efectivo recibido es menor al total.
- Mejor aprovechamiento de pantallas grandes y pequeñas.


## Versión 1.7
- Todos los botones responden a clic y Enter cuando tienen el foco.
- Ticket térmico con logo de Tienda Mejía.
- Selector de ticket 80 mm o 58 mm.
- El ticket se abre en vista imprimible.
- Reportes de Ventas, Cortes de caja e Historial de inventario con Vista imprimible.
- Las vistas imprimibles incluyen logo, título y fecha de generación.


## Versión 1.8
- Corregido el error `name 'ticket_size' is not defined`.
- La impresión del ticket usa 80 mm por defecto y 58 mm solo cuando se selecciona.
- Un fallo de impresión ya no debe impedir el registro de la venta.
- En Reportes, doble clic o Enter sobre una venta abre su detalle imprimible.
- En Cortes de caja, doble clic o Enter abre el corte imprimible.
- En Historial de inventario, doble clic o Enter abre la vista imprimible del reporte.


## Versión 1.9
- Detalle de gastos: doble clic, Enter o botón Ver detalle / imprimir.
- El detalle de gasto muestra solicitante, autorizador, fechas, estado, monto, caja y nota.
- Movimientos manuales de inventario: cortesía/regalo, merma/daño, uso interno y ajustes de gerente.
- Las salidas manuales consumen existencias por FIFO/PEPS y quedan auditadas.
- Presentaciones de producto con equivalencia y precio propios.
- Ejemplo: producto base Bolsita de agua + presentación Bolsón (factor 25).
- Ejemplo: Sopa de vaso base $1.25 + presentación Preparada (factor 1) a $1.50.
- El POS descuenta automáticamente la cantidad base correcta según la presentación vendida.
- La venta y el ticket muestran la presentación elegida.


## Versión 1.9.1
- Corregido el error al agregar productos en Ventas.
- El selector de Presentación ahora aparece realmente en el Punto de Venta.
- Presentación base, bolsón, preparada y otras variantes se cargan al seleccionar el producto.
- El carrito muestra la presentación vendida.
- El botón -1 vuelve a funcionar con presentaciones.
- Los códigos de barras de presentaciones también pueden agregar directamente la variante correcta.
- Los mensajes de error del POS ahora diferencian producto, cantidad y errores internos.


## Versión 2.0
- Los artículos pueden ser Producto (con inventario) o Servicio (sin inventario).
- Ejemplo de servicio: Venta de saldo telefónico.
- Nuevo módulo Adicionales por producto.
- Preparación puede ser un servicio adicional sin inventario.
- Cremora puede configurarse como producto consumido por el adicional.
- El POS suma los adicionales al precio y descuenta inventario únicamente cuando corresponde.
- Los tickets muestran los adicionales seleccionados.


## Versión 2.0.1
- Código de barras de presentaciones realmente opcional; vacío se guarda como NULL.
- Mensajes separados para nombre de presentación duplicado y código de barras duplicado.
- Una presentación desactivada con el mismo nombre puede recuperarse al volverla a registrar.
- Compras ahora permite elegir presentación de compra.
- Cantidad y costo se ingresan por la presentación comprada y el sistema convierte automáticamente a unidades base.
- Ejemplo: Agua, Bolsón x25, 20 bolsones => 500 bolsas al inventario.
- El costo FIFO se guarda por unidad base automáticamente.


## Versión 2.0.2
- Corregida nuevamente la ventana Registrar compra para pantallas de poca altura.
- GUARDAR COMPRA queda en una barra inferior fija y ya no depende de la altura del formulario.
- Se agregó CANCELAR en la misma barra inferior.
- Se conserva la conversión automática de presentaciones de compra.


## Versión 2.0.3
- Corregido definitivamente el pie de la ventana Registrar compra.
- GUARDAR COMPRA se crea explícitamente en la barra inferior fija.
- El botón llama directamente a la función real de registro de compra (save_purchase).
- CANCELAR permanece visible a la izquierda.


## Versión 2.0.4
- Corregido el botón GUARDAR COMPRA que había quedado insertado fuera de la función de compras.
- Los botones reales CANCELAR y GUARDAR COMPRA ahora viven directamente en la barra inferior fija.
- GUARDAR COMPRA aparece a la derecha y CANCELAR a la izquierda.
- Se validó la ubicación del botón dentro de add_purchase y su conexión a save_purchase.


## Versión 2.0.5
- Corregida la tabla Productos: las columnas estaban desplazadas respecto a los datos.
- Se agregan columnas separadas: Precio venta, Vendido, Existencia y Mínimo.
- Vendido muestra las unidades realmente vendidas en ventas completadas.
- Producto/Servicio vuelve a mostrarse en su columna correcta.
- Movimiento inventario cambia a Movimiento / Historial.
- Cada producto ahora muestra su historial completo de movimientos dentro de la misma ventana.
- Se incluyen compras, ventas, ventas por adicional, anulaciones, cortesías, mermas, uso interno y ajustes manuales.
- Los movimientos manuales se muestran inmediatamente después de registrarlos.
- Reportes > Historial inventario incluye botón Actualizar historial y amplía la consulta a 5000 movimientos.


## Versión 2.1.0
- Reportería diaria por defecto: al abrir Reportes se muestra únicamente HOY.
- Filtros rápidos en Ventas, Cortes de caja e Historial inventario:
  Hoy, Ayer, Esta semana y Este mes.
- Rango personalizado Desde / Hasta en formato AAAA-MM-DD.
- Ventas muestra resumen del período: ventas válidas, costo y utilidad bruta.
- Cortes de caja muestra resumen y diferencia acumulada del período.
- Historial de inventario permite filtrar adicionalmente por producto y tipo de movimiento.
- El filtro de movimientos se obtiene de los tipos realmente existentes en la base,
  por lo que incluye también ajustes y movimientos manuales históricos.
- Todas las vistas imprimibles respetan exactamente el rango y filtros visibles.


## Versión 2.1.1
- Corregida la pestaña Historial inventario que podía quedar completamente en blanco.
- La tabla y sus encabezados se dibujan antes de consultar los datos.
- Se agregó manejo visible de errores al cargar el historial.
- Compatibilidad con bases que tengan qty o qty_change en inventory_movements.
- El filtro de Producto ya no depende del campo product_type.
- Filtros Producto y Movimiento siempre quedan visibles.
- Al cambiar Producto o Movimiento el historial se actualiza automáticamente.
- Si hoy no hay movimientos, la tabla queda visible e indica 0 movimientos.


## Versión 2.1.2
- El consolidado del Historial de inventario muestra el valor actual del inventario a costo.
- Se calcula con las existencias restantes de los lotes FIFO.
- Con Producto = Todos, muestra el valor total de la tienda.
- Al seleccionar un producto, muestra el valor actual únicamente de ese producto.


## Versión 2.1.3
- Reportes > Ventas ahora incluye una columna Adicionales.
- Cada venta muestra los adicionales utilizados, por ejemplo Preparación o Cremora.
- Si el mismo adicional aparece varias veces en una venta, se muestra su cantidad.
- La Vista imprimible de Ventas también incluye los adicionales.
- El detalle imprimible de cada venta muestra los adicionales asociados a cada producto.


## Versión 2.3.0 Producción
- Recuperación automática de ventas pendientes ante apagón o cierre inesperado.
- El borrador se guarda en SQLite después de cada cambio del carrito.
- El borrador NO descuenta inventario hasta cobrar la venta.
- Al volver a iniciar sesión se puede Recuperar, Descartar o conservar el borrador.
- SQLite configurado con WAL, synchronous FULL y busy timeout para mayor resistencia.
- Botón ELIMINAR ITEM visible en el punto de venta; la tecla Supr se conserva.
- Nuevo menú Devoluciones para administradores.
- Devolución parcial por artículo con cantidad y motivo.
- La devolución restaura el producto y componentes inventariables de adicionales.
- Reembolsos en efectivo reducen correctamente el efectivo esperado en caja.
- Anulación completa restaura productos y componentes de adicionales.
- No se permite anular una venta que ya tenga devoluciones parciales.
- Reporte de ventas muestra Venta, Devuelto y Neto.


## Versión 2.3.1 Producción
- Corrección visual del Punto de Venta para pantallas 1366x720.
- La barra +1 / -1 / ELIMINAR ITEM / Vaciar venta ahora está fija sobre la tabla.
- El botón ELIMINAR ITEM ya no puede quedar oculto debajo del área visible.
- Se conserva la tecla Supr como atajo.


## Versión 2.4.0 Producción
- Rediseño completo del panel de cobro para una operación más intuitiva.
- Total a cobrar más grande y destacado.
- Forma de pago mediante botones visuales: Efectivo, Transferencia y Otro.
- Campo de efectivo recibido de mayor tamaño y alineado como caja registradora.
- Botón PAGO EXACTO.
- Botones rápidos para $5, $10, $20 y $50.
- Indicador en tiempo real: CAMBIO A ENTREGAR o FALTA PARA COMPLETAR EL PAGO.
- Transferencia/Otro ocultan el campo de efectivo y muestran instrucciones.
- Botón COBRAR más claro con atajo F4.
- Nuevo modal visual propio de Tienda Mejía.
- Venta registrada, pago incompleto y vaciar venta ya usan el nuevo estilo.


## Versión 2.4.1 Producción
- Corrige el error `_tkinter.tkapp object has no attribute root` del nuevo modal.
- Los modales ahora utilizan directamente la ventana principal TiendaMejiaApp.
- Una venta confirmada se limpia del carrito y del borrador inmediatamente después del COMMIT.
- Un error visual o de impresión posterior ya no puede mostrarse como "venta no registrada".
- Se reduce el riesgo de cobrar dos veces una venta después de un error de interfaz.


## Versión 2.4.2 Producción
- Panel de cobro compactado para pantallas 1366x720.
- El campo EFECTIVO RECIBIDO queda visible dentro del área de trabajo.
- Se redujo espacio vertical sin quitar Pago exacto, $5, $10, $20, $50 ni cambio/faltante.
- Botón COBRAR y total siguen destacados, pero ocupan menos altura.


## Versión 2.4.3 Producción
- Corrección estructural definitiva del panel de cobro para 1366x720.
- El panel derecho ahora se divide en tres zonas independientes.
- Zona superior: Total y forma de pago.
- Zona intermedia fija: Efectivo recibido, Pago exacto, $5/$10/$20/$50 y Cambio/Faltante.
- Zona inferior fija: Imprimir ticket y COBRAR.
- Las zonas inferiores se reservan antes que el resumen para impedir que queden ocultas.
- Ya no se depende de reducir fuentes o márgenes para mantener visibles los controles críticos.


## Versión 2.4.4 Producción
- El TOTAL A COBRAR ahora se muestra dentro de la zona fija de cobro.
- Total, efectivo recibido y cambio permanecen visibles simultáneamente.
- Flujo visual más claro: TOTAL -> RECIBIDO -> CAMBIO.
- Se conservan Pago exacto y $5/$10/$20/$50.


## Versión 2.4.5 Producción
- Corrige el panel de cobro vacío de la versión 2.4.4.
- `total_var` y `subtotal_var` se crean antes de ser utilizadas por la interfaz.
- Vuelven a visualizarse Total a cobrar, Efectivo recibido, Pago exacto,
  $5/$10/$20/$50, Cambio/Faltante y Cobrar.
- Se mantiene la distribución optimizada para pantallas 1366x720.


## Versión 2.5.0 Producción
- Corte de caja con confirmación y resultado institucional de Tienda Mejía.
- El modal muestra efectivo esperado, contado, diferencia y resultado.
- Los avisos por gastos pendientes también usan el estilo institucional.
- Productos incorpora botón visible ELIMINAR PRODUCTO.
- Productos con historial se desactivan para conservar ventas, compras, inventario y reportes.
- Solo productos sin historial operativo pueden borrarse físicamente.


## Versión 2.5.1 Producción
- Corrige Inicio en blanco al arrancar.
- Inicio se muestra inmediatamente después de cargar el dashboard.
- Cada módulo se construye de forma independiente para que una incidencia no deje toda la interfaz en blanco.
- Corrige el botón ELIMINAR PRODUCTO: ahora se crea después de su función.
- Rediseño completo de Gestión de caja.
- Caja cerrada: estado, Fondo inicial, accesos rápidos y ABRIR CAJA.
- Caja abierta: Fondo inicial, ventas en efectivo, gastos, devoluciones, transferencias, otros pagos y efectivo esperado.
- Acción institucional REALIZAR CORTE DE CAJA.


## Versión 2.5.2 Producción
- Corrige Caja mostrando valores antiguos después de registrar ventas.
- Cada venta confirmada actualiza inmediatamente el panel de Caja.
- Entrar al menú Caja vuelve a consultar la sesión activa y recalcula todos los valores.
- Se añadió botón ACTUALIZAR y hora de última actualización.
- Inicio se recalcula al entrar.
- Reportes se reconstruye al entrar para mostrar cortes recién cerrados.
- Al abrir/cerrar una caja también se actualizan los módulos relacionados.


## Versión 2.6.0 Producción
- Compras incorpora VER DETALLE / IMPRIMIR y ACTUALIZAR.
- Doble clic o Enter sobre una compra abre un reporte detallado imprimible.
- El reporte de compra incluye proveedor, documento, usuario, productos, cantidades, costos y detalle de ingreso.
- Empleados pueden crear productos nuevos, pero modificar, configurar o eliminar productos queda reservado a Gerencia.
- Se agregó protección defensiva para impedir edición de productos por empleados incluso si se invoca el formulario directamente.
- Compras permite registrar y consultar; no incorpora eliminación de compras.
- Gerencia incorpora HISTORIAL DE ACTIVIDAD por empleado.
- El historial consolida ventas, compras, productos creados, inventario, gastos, caja y devoluciones.
- Historial con filtro de fechas, Este mes, Todo e impresión.


## Versión 2.6.1 Producción
- Empleados pueden crear, modificar y configurar productos, presentaciones, adicionales y movimientos.
- ELIMINAR PRODUCTO continúa reservado exclusivamente a Gerencia.
- Nuevo registro de sesiones de usuario: hora de ingreso y hora de salida.
- Cerrar sesión registra SALIDA; cerrar la aplicación registra CIERRE APLICACION.
- Historial de actividad por empleado incluye Ingreso al sistema y Salida del sistema.
- Devoluciones incorpora una barra fija visible con DEVOLVER ITEM, ANULAR VENTA y ACTUALIZAR.
- Se redujo la altura de la tabla superior de Devoluciones para mejorar uso en 1366x720.


## Versión 2.7.0 Producción
- Gastos / Movimientos financieros ahora se registran directamente en la misma pantalla.
- Formulario integrado: tipo, descripción, monto y nota.
- Empleados ven únicamente sus propios movimientos.
- Doble clic o Enter también respeta la privacidad del usuario logueado.
- Gerencia conserva vista global de todos los movimientos.
- Historial con filtro por fechas y total del período.
- Movimientos de empleados quedan pendientes de aprobación.
- Movimientos de Gerencia quedan aprobados automáticamente.


## Versión 2.8.0 Producción
- Gerencia recupera botones APROBAR y RECHAZAR en Gastos / Movimientos financieros.
- Solo movimientos PENDING pueden ser procesados.
- Aprobar un gasto actualiza inmediatamente Caja, Inicio y Finanzas.
- Rechazar conserva el movimiento para auditoría y no afecta la caja.
- Nuevo módulo FINANZAS exclusivo de Gerencia.
- Finanzas consolida ventas, compras, gastos, devoluciones, aperturas y cortes de caja.
- Resumen: Ingresos, Egresos, Resultado neto y Gastos pendientes.
- Filtros por fecha, accesos Hoy/Ayer/Esta semana/Este mes y filtro por tipo.
- Reporte financiero consolidado imprimible.
- Fondo inicial y corte de caja se muestran como CONTROL y no alteran el resultado neto.


## Versión 2.8.1 Producción
- Mejora general de todas las ventanas emergentes del sistema.
- Mayor ancho y alto útil para mensajes y confirmaciones.
- Contenido principal con desplazamiento vertical cuando es necesario.
- Bloques de detalle con mejor legibilidad y ajuste de altura.
- Los botones permanecen siempre visibles en una barra inferior fija.
- Las ventanas emergentes ahora pueden redimensionarse.
- Atajos: Enter confirma y Escape cierra/cancela.
- Se mantiene el estilo institucional del sistema.


## Versión 2.9.0 Producción
- Nuevo Estado de Resultados dentro de Gerencia > Finanzas.
- Separa flujo de efectivo de rentabilidad real del negocio.
- Ventas brutas menos devoluciones = ventas netas.
- Costo de ventas calculado con el costo FIFO/PEPS registrado en cada venta.
- Las compras no se descuentan directamente de la utilidad: permanecen como inventario hasta venderse.
- Utilidad bruta = ventas netas - costo neto de lo vendido.
- Utilidad neta operativa = utilidad bruta - gastos operativos aprobados.
- Muestra margen bruto y margen neto operativo.
- Las devoluciones reducen ventas y, cuando hay detalle disponible, revierten proporcionalmente costo de venta.
- Estado de Resultados imprimible por el rango de fechas seleccionado.
- El consolidado financiero anterior se conserva como flujo de dinero.


## Versión 2.9.1 Producción
- Barra inferior fija en Gerencia > Finanzas para evitar que los botones de impresión queden ocultos.
- Botón IMPRIMIR INFORME FINANCIERO siempre visible.
- Botón IMPRIMIR ESTADO DE RESULTADOS DETALLADO siempre visible.
- Informe financiero incluye movimientos consolidados y métricas de flujo/rentabilidad.
- Estado de Resultados detallado incluye resumen contable y desglose de ventas, devoluciones, gastos aprobados y compras informativas.
- Las compras se presentan de forma informativa y no se descuentan directamente de la utilidad.


## Versión 2.9.2 Producción
- Nuevo tipo de movimiento: Ingreso de caja.
- Permite registrar efectivo que entra por pagos antiguos, reintegros, aportes u otras razones ajenas a una venta.
- Requiere una jornada de caja abierta para mantener correcto el arqueo.
- Se registra concepto, monto, nota, usuario, fecha y caja.
- El ingreso aumenta el efectivo esperado del corte.
- Aparece en el historial del empleado y en la vista global de Gerencia.
- Aparece en Finanzas como ingreso de efectivo.
- No se suma a las ventas ni a la utilidad operativa del Estado de Resultados.
- El Estado de Resultados Detallado lo muestra en una sección informativa separada.
- Se corrigió el cálculo del costo devuelto usando cost_amount de sale_return_items.

## Versión 2.9.3 Producción
- Doble clic o Enter en el historial de inventario abre detalle completo.
- Incluye producto, códigos, unidad, fecha/hora, tipo, dirección, cantidad, costo, valor, referencia, usuario y nota.
- Si el movimiento proviene de compra, venta o devolución, muestra también el documento relacionado.
