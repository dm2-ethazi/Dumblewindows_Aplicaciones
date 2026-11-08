package com.dm2.dumbledroid

/**
 * Dirección del servidor y rutas compartidas con ApiService.kt.
 * No contiene credenciales: la API key llega desde BuildConfig al cliente HTTP.
 * Cambiar una ruta exige revisar la anotación GET y sus parámetros Path/Query.
 * PATH_ID pertenece al método heredado no usado; la consulta activa por ID
 * declara su ruta directamente en getEstudianteRaw.
 *
 * @author Kenneth Alvarez
 */
object Constantes {
    const val Base_URL = "https://dumblewindows-api.tail6bccfa.ts.net"
    const val PATH_DATOS = "/estudiantes"
    const val PATH_ID = "/estudiantes/{student_id}"
}
