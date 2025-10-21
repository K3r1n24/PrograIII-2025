import crud_academico

db = crud_academico.crud()

class crud_alumno:
    def consultar(self, buscar):
        return db.consultar("SELECT * FROM alumnos WHERE nombre like '%"+ buscar +"%'")
    
    def administrar(self, datos):
        if datos['accion']=="nuevo":
            sql = """
                INSERT INTO alumnos (codigo, nombre, direccion, telefono, email)
                VALUES (%s, %s, %s, %s, %s)
            """
            valores = (datos['codigo'], datos['nombre'], datos['direccion'], datos['telefono'], datos['email'])
        if datos['accion']=="modificar":
            sql = """
                UPDATE alumnos SET codigo=%s, nombre=%s, direccion=%s, telefono=%s, email=%s
                WHERE idAlumno=%s
            """
            valores = (datos['codigo'], datos['nombre'], datos['direccion'], datos['telefono'], datos['email'], datos['idAlumno'])
        if datos['accion']=="eliminar":
            sql = "DELETE FROM alumnos WHERE idAlumno=%s"
            valores = (datos['idAlumno'],)
        return db.ejecutar(sql, valores)