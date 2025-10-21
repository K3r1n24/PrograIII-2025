from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib import parse
from urllib.parse import urlparse, parse_qs
import json 
import crud_alumno
import crud  # Cambiado de crud_academico a crud

port = 3000

crudAlumno = crud_alumno.crud_alumno()
crudUsuario = crud.crud_usuario()  # Añadido

class miServidor(SimpleHTTPRequestHandler):
    def do_GET(self):
        url_parseada = urlparse(self.path)
        path = url_parseada.path
        parametros = parse_qs(url_parseada.query)

        if self.path == "/":
            self.path = "index.html"  # Cambiado: raíz va a index.html, pero en index.html añadí login como primera vista
            return SimpleHTTPRequestHandler.do_GET(self)
        if self.path == "/alumnos":
            alumnos = crudAlumno.consultar("")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(alumnos).encode('utf-8'))
        if path == "/vistas":
            self.path = '/modulos/' + parametros['form'][0] + '.html'
            return SimpleHTTPRequestHandler.do_GET(self)
        # Añadidos para usuarios
        if path == "/usuarios":
            usuarios = crudUsuario.consultar(parametros.get('buscar', [''])[0])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(usuarios).encode('utf-8'))
    
    def do_POST(self):
        longitud = int(self.headers['Content-Length'])
        datos = self.rfile.read(longitud)
        datos = datos.decode("utf-8")
        datos = parse.unquote(datos)
        datos = json.loads(datos)
        resp = {"msg": crudAlumno.administrar(datos)}
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))
        # Añadidos para usuarios
        if path == "/administrar_usuario":
            resp = {"msg": crudUsuario.administrar(datos)}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        if path == "/verificar_login":
            usuarios = crudUsuario.consultar(datos.get('usuario', ''))
            encontrado = False
            for u in usuarios:
                if u['usuario'] == datos.get('usuario') and u['clave'] == datos.get('clave'):
                    encontrado = True
                    break
            resp = {"acceso": encontrado}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))

print("Servidor ejecutandose en el puerto", port)
server = HTTPServer(("localhost", port), miServidor)
server.serve_forever()
