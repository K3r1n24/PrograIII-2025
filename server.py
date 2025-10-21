from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib import parse
from urllib.parse import urlparse, parse_qs
import json 
import crud_alumno

port = 3000

crudAlumno = crud_alumno.crud_alumno()

class miServidor(SimpleHTTPRequestHandler):
    def do_GET(self):
        url_parseada = urlparse(self.path)
        path = url_parseada.path
        parametros = parse_qs(url_parseada.query)

        if self.path=="/":
            self.path="index.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        if self.path=="/alumnos":
            alumnos = crudAlumno.consultar("")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(alumnos).encode('utf-8'))
        if path=="/vistas":
            self.path = '/modulos/'+ parametros['form'][0] +'.html'
            return SimpleHTTPRequestHandler.do_GET(self)
    
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

print("Servidor ejecutandose en el puerto", port)
server = HTTPServer(("localhost", port), miServidor)
server.serve_forever()