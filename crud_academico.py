import mysql.connector

class crud:
    def __init__(self):
        try:
            self.conn = mysql.connector.connect(
                host="localhost",
                user="root",         
                password="",         
                database="db_academica"  
            )
            self.cursor = self.conn.cursor(dictionary=True)
            print("✅ Conexión con la base de datos establecida correctamente.")
        except Exception as e:
            print("❌ Error al conectar con la base de datos:", e)

    def consultar(self, sql):
        try:
            self.cursor.execute(sql)
            return self.cursor.fetchall()
        except Exception as e:
            print("❌ Error al consultar:", e)
            return []

    def ejecutar(self, sql, valores=None):
        try:
            self.cursor.execute(sql, valores)
            self.conn.commit()
            return "Operación realizada correctamente"
        except Exception as e:
            print("❌ Error al ejecutar:", e)
            return str(e)

class crud_usuario:
    def consultar(self, buscar):
        return db.consultar("SELECT * FROM usuarios WHERE nombre LIKE '%" + buscar + "%' OR usuario LIKE '%" + buscar + "%'")
    
    def administrar(self, datos):
        if datos['accion'] == "nuevo":
            sql = """
                INSERT INTO usuarios (usuario, clave, nombre, direccion, telefono)
                VALUES (%s, %s, %s, %s, %s)
            """
            valores = (datos['usuario'], datos['clave'], datos['nombre'], datos['direccion'], datos['telefono'])
        elif datos['accion'] == "modificar":
            sql = """
                UPDATE usuarios SET usuario=%s, clave=%s, nombre=%s, direccion=%s, telefono=%s
                WHERE idUsuario=%s
            """
            valores = (datos['usuario'], datos['clave'], datos['nombre'], datos['direccion'], datos['telefono'], datos['idUsuario'])
        elif datos['accion'] == "eliminar":
            sql = "DELETE FROM usuarios WHERE idUsuario=%s"
            valores = (datos['idUsuario'],)
        else:
            return "Acción no válida"
        return db.ejecutar(sql, valores)