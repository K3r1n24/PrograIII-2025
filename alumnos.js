 var accion = "nuevo",
    idAlumno = 0;
document.addEventListener("DOMContentLoaded", event=>{ 
    frmAlumnos.addEventListener("submit",e=>{
        e.preventDefault();

        guardarAlumnos();
    });
    obtenerAlumnos();
});
async function guardarAlumnos(){
    let datos = {
        accion,
        idAlumno,
        codigo: txtCodigoAlumno.value,
        nombre: txtNombreAlumno.value,
        direccion: txtDireccionAlumno.value,
        telefono: txtTelefonoAlumno.value,
        email: txtEmailAlumno.value
    };
    let response = await fetch("/alumnos",{
        method: "POST",
        body: JSON.stringify(datos),
    }), 
        respuesta = await response.json();
    if(respuesta.msg!="ok"){
        alertify.error(`Error al procesar alumno: ${respuesta}`);
        return;
    }
    limpiarFormulario();
    obtenerAlumnos();
}
function limpiarFormulario(){
    accion = "nuevo";
    idAlumno = 0;
    txtCodigoAlumno.value = "";
    txtNombreAlumno.value = "";
    txtDireccionAlumno.value = "";
    txtTelefonoAlumno.value = "";
    txtEmailAlumno.value = "";
}
async function obtenerAlumnos(){
    let response = await fetch("/alumnos"), 
        respuesta = await response.json();
    mostrarDatosAlumnos(respuesta);
}
function mostrarDatosAlumnos(alumnos){
    let filas = "";
    alumnos.forEach(alumno=>{
        filas += `
            <tr onClick='mostrarAlumno(${ JSON.stringify(alumno) })'>
                <td>${alumno.codigo}</td>
                <td>${alumno.nombre}</td>
                <td>${alumno.direccion}</td>
                <td>${alumno.telefono}</td>
                <td>${alumno.email}</td>
                <td><button onClick='eliminarAlumno(${ JSON.stringify(alumno) }, event)' class="btn btn-danger btn-sm">ELIMINAR</button></td>
            </tr>
        `;
    });
    tblAlumnos.innerHTML = filas;
}
function mostrarAlumno(alumno){
    accion = "modificar";
    idAlumno = alumno.idAlumno;
    txtCodigoAlumno.value = alumno.codigo;
    txtNombreAlumno.value = alumno.nombre;
    txtDireccionAlumno.value = alumno.direccion;
    txtTelefonoAlumno.value = alumno.telefono;
    txtEmailAlumno.value = alumno.email;
}
function eliminarAlumno(alumno, event){
    event.preventDefault();

    if(confirm(`Esta seguro de eliminar a ${alumno.nombre}`)){
        idAlumno = alumno.idAlumno;
        accion = "eliminar";
        guardarAlumnos();
    }
}