# Importaciones necesarias para la aplicación Flask
import os
import json
import random
import string
from functools import wraps
from datetime import timedelta, datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

# Importaciones de Firebase/Firestore/Auth
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Query
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================================================================
# 1. CONFIGURACIÓN INICIAL DE FLASK Y FIREBASE
# ==============================================================================

# Inicialización de Flask
app = Flask(__name__)

# Configuración de variables de sesión y mensajes flash
SECRET_KEY = os.getenv('SECRET_KEY', 'SUPER_SECRETO_FLIA_2025_UGB')
app.secret_key = SECRET_KEY
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
app.config['STATIC_FOLDER'] = 'static'

# Inicialización de Firebase
try:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase inicializado correctamente.")
except Exception as e:
    print(f"Error al inicializar Firebase: {e}. Asegúrate de que 'serviceAccountKey.json' existe.")
    db = None

# ==============================================================================
# 2. DECORADORES Y UTILIDADES
# ==============================================================================

def requires_auth(role_required):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'logged_in' not in session or not session['logged_in']:
                flash('Debes iniciar sesión para acceder a esta página.', 'error')
                return redirect(url_for('index'))
            
            user_role = session.get('user_role')
            if user_role != role_required:
                flash(f'Acceso denegado. Se requiere el rol de {role_required}.', 'error')
                if user_role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif user_role == 'juez':
                    return redirect(url_for('juez_dashboard'))
                elif user_role == 'participante':
                    return redirect(url_for('participante_dashboard'))
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def db_connected():
    return db is not None

def get_user_info(user_id):
    if not db_connected():
        return {'user_name': 'Usuario Desconocido', 'rol': 'desconocido'}
    try:
        user_doc = db.collection('usuarios').document(user_id).get()
        if user_doc.exists:
            data = user_doc.to_dict()
            first_name = data.get('nombre', '').strip()
            last_name = data.get('apellido', '').strip()
            user_name = f"{first_name} {last_name}".strip() or first_name or user_id
            return {'user_name': user_name, 'rol': data.get('rol', 'participante'), 'data': data}
    except Exception as e:
        print(f"Error al obtener info de usuario {user_id}: {e}")
    return {'user_name': user_id, 'rol': 'desconocido', 'data': {}}

def contar_proyectos_por_juez(juez_id):
    """Cuenta cuántos proyectos tiene asignado un juez"""
    if not db_connected():
        return 0
    try:
        count = 0
        proyectos_ref = db.collection('proyectos').where('juez_asignado', '==', juez_id)
        proyectos = proyectos_ref.stream()
        for _ in proyectos:
            count += 1
        return count
    except Exception as e:
        print(f"Error contando proyectos del juez {juez_id}: {e}")
        return 0

def get_users_by_role(role):
    """Obtiene todos los usuarios de un rol específico con información completa"""
    if not db_connected():
        return []
    
    try:
        users = []
        users_ref = db.collection('usuarios').where('rol', '==', role).stream()
        
        for doc in users_ref:
            user_data = doc.to_dict()
            user_data['id'] = doc.id
            
            if role == 'juez':
                user_data['proyectos_asignados'] = contar_proyectos_por_juez(doc.id)
            
            if role == 'participante':
                grupo_id = user_data.get('grupo_asignado')
                grupo_encontrado = False
                
                if grupo_id:
                    try:
                        grupo_doc = db.collection('grupos').document(grupo_id).get()
                        if grupo_doc.exists:
                            grupo_data = grupo_doc.to_dict()
                            user_data['grupo_nombre'] = grupo_data.get('nombre', 'Sin nombre')
                            user_data['grupo_codigo'] = grupo_data.get('codigo', 'N/A')
                            user_data['categoria'] = grupo_data.get('categoria', 'Sin categoría')
                            user_data['grupo_id'] = grupo_id
                            grupo_encontrado = True
                    except Exception as e:
                        print(f"Error al obtener grupo por grupo_asignado: {e}")
                
                if not grupo_encontrado:
                    try:
                        grupos_ref = db.collection('grupos').where('miembros', 'array_contains', doc.id).limit(1).stream()
                        grupo_doc = next(grupos_ref, None)
                        
                        if grupo_doc:
                            grupo_data = grupo_doc.to_dict()
                            user_data['grupo_nombre'] = grupo_data.get('nombre', 'Sin nombre')
                            user_data['grupo_codigo'] = grupo_data.get('codigo', 'N/A')
                            user_data['categoria'] = grupo_data.get('categoria', 'Sin categoría')
                            user_data['grupo_id'] = grupo_doc.id
                            grupo_encontrado = True
                            
                            try:
                                db.collection('usuarios').document(doc.id).update({
                                    'grupo_asignado': grupo_doc.id
                                })
                            except Exception as e:
                                print(f"⚠️ Error al actualizar grupo_asignado: {e}")
                    except Exception as e:
                        print(f"❌ Error al buscar grupo por miembros: {e}")
                
                if not grupo_encontrado:
                    user_data['grupo_nombre'] = 'Sin grupo'
                    user_data['grupo_codigo'] = 'N/A'
                    user_data['categoria'] = 'Sin categoría'
                    user_data['grupo_id'] = None
            
            users.append(user_data)
        
        return users
        
    except Exception as e:
        print(f"Error al obtener usuarios por rol: {e}")
        return []

def get_all_grupos():
    """Obtiene todos los grupos con información completa"""
    if not db_connected():
        return []
    
    try:
        grupos = []
        grupos_docs = list(db.collection('grupos').stream())
        
        for doc in grupos_docs:
            grupo_data = doc.to_dict()
            grupo_data['id'] = doc.id
            
            miembros_ids = grupo_data.get('miembros', [])
            grupo_data['num_miembros'] = len(miembros_ids)
            
            miembros_info = []
            for miembro_id in miembros_ids:
                try:
                    miembro_data = get_user_info(miembro_id)
                    miembros_info.append({
                        'id': miembro_id,
                        'nombre': miembro_data['user_name'],
                        'es_lider': (miembro_id == grupo_data.get('lider_id'))
                    })
                except Exception as e:
                    miembros_info.append({
                        'id': miembro_id,
                        'nombre': 'Usuario Desconocido',
                        'es_lider': False
                    })
            
            grupo_data['miembros_info'] = miembros_info
            
            try:
                proyecto_doc = db.collection('proyectos').document(doc.id).get()
                
                if proyecto_doc.exists:
                    proyecto = proyecto_doc.to_dict()
                    grupo_data['tiene_proyecto'] = True
                    grupo_data['proyecto_titulo'] = proyecto.get('titulo', 'Sin título')
                    grupo_data['proyecto_descripcion'] = proyecto.get('resumen', 'Sin descripción')
                    
                    categoria_proyecto = proyecto.get('categoria')
                    if categoria_proyecto:
                        grupo_data['categoria'] = categoria_proyecto
                    elif not grupo_data.get('categoria'):
                        grupo_data['categoria'] = 'Sin categoría'
                    
                    juez_id = proyecto.get('juez_asignado')
                    if juez_id:
                        try:
                            juez_info = get_user_info(juez_id)
                            grupo_data['juez_nombre'] = juez_info['user_name']
                            grupo_data['juez_id'] = juez_id
                        except Exception as e:
                            grupo_data['juez_nombre'] = None
                            grupo_data['juez_id'] = None
                    else:
                        grupo_data['juez_nombre'] = None
                        grupo_data['juez_id'] = None
                else:
                    grupo_data['tiene_proyecto'] = False
                    grupo_data['proyecto_titulo'] = grupo_data.get('nombre', 'Sin proyecto')
                    grupo_data['proyecto_descripcion'] = 'El líder del grupo aún no ha registrado el proyecto'
                    grupo_data['juez_nombre'] = None
                    grupo_data['juez_id'] = None
                    
                    if not grupo_data.get('categoria'):
                        grupo_data['categoria'] = 'Sin categoría'
            except Exception as e:
                grupo_data['tiene_proyecto'] = False
                grupo_data['proyecto_titulo'] = 'Error al cargar'
                grupo_data['proyecto_descripcion'] = 'Error al obtener información del proyecto'
                grupo_data['juez_nombre'] = None
                grupo_data['juez_id'] = None
                
            fecha_creacion = grupo_data.get('fecha_creacion')
            if fecha_creacion:
                try:
                    if hasattr(fecha_creacion, 'strftime'):
                        grupo_data['fecha_registro'] = fecha_creacion.strftime('%d/%m/%Y')
                    else:
                        grupo_data['fecha_registro'] = str(fecha_creacion)
                except:
                    grupo_data['fecha_registro'] = 'N/A'
            else:
                grupo_data['fecha_registro'] = 'N/A'
            
            grupos.append(grupo_data)
        
        return grupos
        
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO al obtener grupos: {e}")
        return []

def get_rubrica_activa():
    """Obtiene la única rúbrica marcada como activa."""
    if not db_connected():
        return None
    try:
        rubrica_ref = db.collection('rubricas').where('activa', '==', True).limit(1).stream()
        for doc in rubrica_ref:
            rubrica_data = doc.to_dict()
            rubrica_data['id'] = doc.id
            return rubrica_data
            
        return None
    except Exception as e:
        print(f"Error al obtener la rúbrica activa: {e}")
        return None

def obtener_categoria_juez(juez_email):
    """Obtiene la categoría asignada a un juez"""
    if not db_connected():
        return None
    try:
        juez_ref = db.collection('usuarios').document(juez_email).get()
        if juez_ref.exists:
            juez_data = juez_ref.to_dict()
            categoria = juez_data.get('categoria_asignada')
            return categoria
        return None
    except Exception as e:
        print(f"Error al obtener categoría del juez: {e}")
        return None

def calcular_promedio_evaluaciones_dinamico(grupo_id):
    """Calcula el promedio de las evaluaciones usando la estructura dinámica"""
    if not db_connected():
        return 0.0, []
        
    rubrica = get_rubrica_activa()
    if not rubrica:
        return 0.0, []

    try:
        evaluaciones_ref = db.collection('proyectos').document(grupo_id).collection('evaluaciones').stream()
        scores_porcentaje = []
        evaluaciones_list = []
        
        for eval_doc in evaluaciones_ref:
            eval_data = eval_doc.to_dict()
            eval_data['evaluacion_id'] = eval_doc.id
            
            puntaje_total_evaluacion = 0.0

            if 'puntuaciones_criterios' in eval_data:
                for key, puntaje in eval_data['puntuaciones_criterios'].items():
                    criterio_nombre = key
                    meta = next((c for c in rubrica['criterios'] if c['nombre'] == criterio_nombre), None)

                    if meta:
                        peso_porcentaje = meta['porcentaje'] / 100
                        puntos_max = meta['puntos_maximos']
                        puntos_obtenidos = puntaje.get('puntos_obtenidos', 0)

                        if puntos_max > 0:
                            contribucion = (float(puntos_obtenidos) / float(puntos_max)) * peso_porcentaje
                            puntaje_total_evaluacion += contribucion
                    
                scores_porcentaje.append(puntaje_total_evaluacion * 100)
            
            elif 'puntuacion_criterio_1' in eval_data and 'puntuacion_criterio_2' in eval_data:
                score1 = eval_data.get('puntuacion_criterio_1', 0)
                score2 = eval_data.get('puntuacion_criterio_2', 0)
                total_score_obtenido = float(score1) + float(score2)
                puntaje_porcentaje = (total_score_obtenido / 20.0) * 100.0 if 20.0 > 0 else 0.0
                scores_porcentaje.append(puntaje_porcentaje)

            evaluaciones_list.append(eval_data)
        
        num_evaluaciones = len(scores_porcentaje)
        if num_evaluaciones > 0:
            promedio = sum(scores_porcentaje) / num_evaluaciones
            return round(promedio, 2), evaluaciones_list
        
        return 0.0, evaluaciones_list
        
    except Exception as e:
        print(f"Error al calcular promedio de evaluaciones para {grupo_id}: {e}")
        return 0.0, []

def get_all_projects_with_status(juez_id=None):
    if not db_connected():
        return []
    projects = []
    try:
        for project_doc in db.collection('proyectos').stream():
            project_data = project_doc.to_dict()
            project_id = project_doc.id
            
            promedio, evaluaciones_list = calcular_promedio_evaluaciones_dinamico(project_id)
            
            num_evaluations = len(evaluaciones_list)
            
            project_data['id'] = project_id
            project_data['num_evaluaciones'] = num_evaluations
            project_data['promedio_score'] = promedio
            project_data['scores'] = [e.get('puntuacion_final', 0) for e in evaluaciones_list]
            
            project_data['ya_evaluado'] = False
            for evaluation in evaluaciones_list:
                if evaluation.get('juez_email') == juez_id or evaluation.get('juez_id') == juez_id:
                    project_data['ya_evaluado'] = True
                    project_data['mi_evaluacion'] = evaluation
                    break

            grupo_doc = db.collection('grupos').document(project_id).get()
            if grupo_doc.exists:
                 project_data['nombre_equipo'] = grupo_doc.to_dict().get('nombre', 'Grupo Desconocido')
            else:
                 project_data['nombre_equipo'] = 'Grupo Desconocido'

            projects.append(project_data)
            
        return sorted(projects, key=lambda p: p['promedio_score'], reverse=True)
    except Exception as e:
        print(f"Error al obtener proyectos: {e}")
        return []

def is_feria_abierta():
    if not db_connected():
        return True
    try:
        config_doc = db.collection('configuracion').document('feria').get()
        return config_doc.to_dict().get('feria_abierta', True) if config_doc.exists else True
    except:
        return True

def is_ediciones_habilitadas():
    if not db_connected():
        return False
    try:
        config_doc = db.collection('configuracion').document('feria').get()
        return config_doc.to_dict().get('ediciones_habilitadas', False) if config_doc.exists else False
    except:
        return False

def obtener_tema_actual():
    if not db_connected():
        return 'claro'
    try:
        config_doc = db.collection('configuracion').document('feria').get()
        return config_doc.to_dict().get('tema', 'claro') if config_doc.exists else 'claro'
    except:
        return 'claro'

# ==============================================================================
# 3. RUTAS DE NAVEGACIÓN Y AUTENTICACIÓN
# ==============================================================================

@app.route('/', methods=['GET', 'POST'])
def index():
    if session.get('logged_in'):
        role = session.get('user_role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'juez':
            return redirect(url_for('juez_dashboard'))
        elif role == 'participante':
            return redirect(url_for('participante_dashboard'))
    
    if request.method == 'POST':
        cuenta = request.form.get('cuenta_universidad')
        password = request.form.get('password')
        form_type = request.form.get('form_type', 'participante')
        
        if not cuenta or not password:
            flash('Debe ingresar su cuenta/correo y contraseña.', 'error')
            return redirect(url_for('index'))

        if db_connected():
            try:
                user_doc = db.collection('usuarios').document(cuenta).get()
                if not user_doc.exists:
                    flash('Credenciales inválidas. Verifique su cuenta/correo y contraseña.', 'error')
                    return redirect(url_for('index'))

                user_data = user_doc.to_dict()
                stored_hash = user_data.get('password_hash')
                user_role = user_data.get('rol', 'participante')

                if form_type == 'participante' and user_role in ['admin', 'juez']:
                    flash('Por favor, use la pestaña "Juez/Admin" para iniciar sesión.', 'error')
                    return redirect(url_for('index'))
                
                if form_type == 'juez_admin' and user_role == 'participante':
                    flash('Por favor, use la pestaña "Participante" para iniciar sesión.', 'error')
                    return redirect(url_for('index'))

                if check_password_hash(stored_hash, password):
                    session['logged_in'] = True
                    session['user_id'] = cuenta
                    session['user_role'] = user_role
                    session['cuenta'] = cuenta
                    session['user_name'] = get_user_info(cuenta)['user_name']
                    
                    session['just_logged_in'] = True
                    
                    if user_role == 'administrador':
                        return redirect(url_for('admin_dashboard'))
                    elif user_role == 'juez':
                        return redirect(url_for('juez_dashboard'))
                    else:
                        return redirect(url_for('participante_dashboard'))
                else:
                    flash('Credenciales inválidas. Verifique su cuenta/correo y contraseña.', 'error')
                    return redirect(url_for('index'))

            except Exception as e:
                print(f"Error en login: {e}")
                flash('Ocurrió un error al intentar iniciar sesión. Intente más tarde.', 'error')
                return redirect(url_for('index'))
        else:
            flash('Servicio temporalmente no disponible. Por favor, intenta más tarde.', 'error')
            return redirect(url_for('index'))
        
    return render_template('index.html', db_connected=db_connected())

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        cuenta_universidad = request.form.get('cuenta_universidad')
        password = request.form.get('password')
        ciclo = request.form.get('ciclo')
        
        if not all([nombre, apellido, cuenta_universidad, password, ciclo]):
            flash('Todos los campos son obligatorios.', 'error')
            return redirect(url_for('registro'))
        
        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres.", 'error')
            return redirect(url_for('registro'))
        
        if db_connected():
            try:
                doc_ref = db.collection('usuarios').document(cuenta_universidad)
                if doc_ref.get().exists:
                    flash('La cuenta universitaria ya se encuentra registrada.', 'error')
                    return redirect(url_for('registro'))
                
                password_hash = generate_password_hash(password)
                user_data = {
                    'nombre': nombre,
                    'apellido': apellido,
                    'cuenta': cuenta_universidad,
                    'correo': cuenta_universidad,
                    'ciclo': ciclo,
                    'rol': 'participante',
                    'fecha_registro': firestore.SERVER_TIMESTAMP,
                    'password_hash': password_hash
                }
                doc_ref.set(user_data)
                flash('¡Registro exitoso! Ahora puedes iniciar sesión.', 'success')
                return redirect(url_for('index'))
            
            except Exception as e:
                print(f"Error al registrar: {e}")
                flash('Ocurrió un error al intentar registrar la cuenta. Intente con otra cuenta universitaria.', 'error')
                return redirect(url_for('registro'))
        else:
            flash('Servicio temporalmente no disponible. Por favor, intenta más tarde.', 'error')
            return redirect(url_for('registro'))

    return render_template('registro.html')

# ==============================================================================
# 4. RUTAS DE DASHBOARDS
# ==============================================================================

@app.route('/admin/dashboard')
@requires_auth('admin')
def admin_dashboard():
    user_info = get_user_info(session.get('user_id'))
    participantes = get_users_by_role('participante')
    jueces = get_users_by_role('juez')
    proyectos = get_all_projects_with_status()
    grupos = get_all_grupos()
    
    todos_grupos = []
    if db_connected():
        try:
            grupos_ref = db.collection('grupos').stream()
            for doc in grupos_ref:
                grupo_data = doc.to_dict()
                grupo_data['id'] = doc.id
                todos_grupos.append(grupo_data)
        except Exception as e:
            print(f"Error al obtener grupos: {e}")
    
    grupos_stats = {
    'total': len(grupos),
    'con_proyecto': sum(1 for g in grupos if g.get('tiene_proyecto')),
    'con_juez': sum(1 for g in grupos if g.get('juez_nombre')),
    'sin_proyecto': sum(1 for g in grupos if not g.get('tiene_proyecto')),
    'programacion': sum(1 for g in grupos if g.get('categoria') and 'program' in g.get('categoria', '').lower()),
    'electronica': sum(1 for g in grupos if g.get('categoria') and 'electron' in g.get('categoria', '').lower()),
    'robotica': sum(1 for g in grupos if g.get('categoria') and 'robot' in g.get('categoria', '').lower()),
    'ingenieria': sum(1 for g in grupos if g.get('categoria') and 'ingenier' in g.get('categoria', '').lower()) 
    }

    evaluaciones = []
    if db_connected():
        try:
            for p in proyectos:
                p_id = p['id']
                evals_ref = db.collection('proyectos').document(p_id).collection('evaluaciones').stream()
                for e in evals_ref:
                    edata = e.to_dict()
                    juez_email = edata.get('juez_email') or e.id
                    juez_info = get_user_info(juez_email)

                    puntuacion_final = edata.get('puntuacion_final')
                    
                    evaluaciones.append({
                        'proyecto_titulo': p.get('titulo'),
                        'proyecto_id': p_id,
                        'grupo_nombre': p.get('nombre_equipo') or p.get('participante_nombre'),
                        'juez_nombre': juez_info['user_name'],
                        'juez_id': juez_email,
                        'puntuacion_criterio_1': edata.get('puntuacion_criterio_1', 0),
                        'puntuacion_criterio_2': edata.get('puntuacion_criterio_2', 0),
                        'puntuacion_final': puntuacion_final if puntuacion_final is not None else (edata.get('puntuacion_criterio_1', 0) + edata.get('puntuacion_criterio_2', 0)),
                        'fecha_evaluacion': edata.get('fecha_evaluacion')
                    })
        except Exception as e:
            print(f"Error al cargar evaluaciones en admin dashboard: {e}")

    return render_template('admin_dashboard.html',
                           user_name=user_info['user_name'],
                           participantes=participantes,
                           jueces=jueces,
                           proyectos=proyectos,
                           grupos=grupos,
                           grupos_stats=grupos_stats,
                           todos_grupos=todos_grupos,
                           evaluaciones=evaluaciones,
                           get_user_info=get_user_info,
                           seccion_activa=request.args.get('section', 'dashboard'),
                           tema=obtener_tema_actual())

@app.route('/admin/gestion-equipos')
@requires_auth('admin')
def gestion_equipos():
    return redirect(url_for('admin_dashboard', section='equipos'))

# ==============================================================================
# RUTA DEL JUEZ DASHBOARD - CORREGIDA
# ==============================================================================

@app.route('/juez/dashboard')
@requires_auth('juez')
def juez_dashboard():
    try:
        user_id = session.get('user_id')
        user_info = get_user_info(user_id)
        
        # Obtener la categoría asignada al juez
        categoria_asignada = None
        if db_connected():
            try:
                juez_doc = db.collection('usuarios').document(user_id).get()
                if juez_doc.exists:
                    juez_data = juez_doc.to_dict()
                    categoria_asignada = juez_data.get('categoria_asignada', 'Sin categoría')
                    session['categoria_asignada'] = categoria_asignada
            except Exception as e:
                print(f"Error al obtener categoría del juez: {e}")
                categoria_asignada = 'Sin categoría'
        else:
            categoria_asignada = 'Sin conexión a BD'
        
        # Obtener proyectos de la categoría del juez
        proyectos_asignados = []
        total_proyectos = 0
        evaluados_count = 0
        
        if db_connected() and categoria_asignada and categoria_asignada != 'Sin categoría':
            try:
                # Buscar proyectos por categoría
                proyectos_ref = db.collection('proyectos').where('categoria', '==', categoria_asignada).stream()
                
                for doc in proyectos_ref:
                    proyecto_data = doc.to_dict()
                    proyecto_data['id'] = doc.id
                    
                    # Obtener información del grupo
                    try:
                        grupo_doc = db.collection('grupos').document(doc.id).get()
                        if grupo_doc.exists:
                            grupo_data = grupo_doc.to_dict()
                            proyecto_data['nombre_equipo'] = grupo_data.get('nombre', 'Sin nombre')
                            proyecto_data['descripcion'] = grupo_data.get('descripcion', '')
                    except Exception as e:
                        proyecto_data['nombre_equipo'] = 'Sin nombre'
                        proyecto_data['descripcion'] = ''
                    
                    # Verificar si este juez ya evaluó este proyecto
                    evaluacion_ref = db.collection('proyectos').document(doc.id).collection('evaluaciones').document(user_id).get()
                    
                    if evaluacion_ref.exists:
                        evaluacion_data = evaluacion_ref.to_dict()
                        proyecto_data['evaluado'] = True
                        proyecto_data['puntuacion_juez'] = evaluacion_data.get('puntuacion_final', 0)
                        proyecto_data['fecha_evaluacion'] = evaluacion_data.get('fecha_evaluacion', '')
                        evaluados_count += 1
                    else:
                        proyecto_data['evaluado'] = False
                        proyecto_data['puntuacion_juez'] = None
                        proyecto_data['fecha_evaluacion'] = None
                    
                    proyectos_asignados.append(proyecto_data)
                    total_proyectos += 1
                    
            except Exception as e:
                print(f"Error al obtener proyectos del juez: {e}")
                flash('Error al cargar proyectos asignados', 'error')
        
        # Calcular estadísticas
        pendientes_count = total_proyectos - evaluados_count
        progreso = round((evaluados_count / total_proyectos * 100) if total_proyectos > 0 else 0, 1)
        
        estadisticas = {
            'total': total_proyectos,
            'evaluados': evaluados_count,
            'pendientes': pendientes_count,
            'progreso': progreso
        }
        
        # Obtener rúbrica activa para mostrar criterios
        rubrica = get_rubrica_activa()
        criterios = rubrica['criterios'] if rubrica else []
        
        # Obtener tema actual
        tema = obtener_tema_actual()
        
        return render_template('juez_dashboard.html',
                               user_name=user_info['user_name'],
                               categoria_juez=categoria_asignada or 'Sin categoría asignada',
                               proyectos=proyectos_asignados,
                               estadisticas=estadisticas,
                               criterios=criterios,
                               tema=tema)
    
    except Exception as e:
        print(f"❌ ERROR en juez_dashboard: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al cargar el dashboard del juez', 'danger')
        return redirect(url_for('index'))

# ==============================================================================
# RUTAS DE EVALUACIÓN PARA JUECES
# ==============================================================================

@app.route('/juez/evaluar/<grupo_id>')
@requires_auth('juez')
def evaluar_proyecto(grupo_id):
    """Muestra el formulario de evaluación para un proyecto específico"""
    try:
        juez_email = session.get('user_id')
        categoria_asignada = session.get('categoria_asignada')
        
        if not categoria_asignada:
            categoria_asignada = obtener_categoria_juez(juez_email)
            session['categoria_asignada'] = categoria_asignada
        
        proyecto_ref = db.collection('proyectos').document(grupo_id).get()
        
        if not proyecto_ref.exists:
            flash('Proyecto no encontrado', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        proyecto_data = proyecto_ref.to_dict()
        proyecto_data['id'] = grupo_id
        
        # VERIFICACIÓN: El juez solo puede evaluar proyectos de su categoría
        proyecto_categoria = proyecto_data.get('categoria')
        if proyecto_categoria != categoria_asignada:
            flash(f'No tienes permiso para evaluar proyectos de {proyecto_categoria}. Tu categoría es: {categoria_asignada}', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        # Obtener nombre del grupo
        grupo_ref = db.collection('grupos').document(grupo_id).get()
        if grupo_ref.exists:
            grupo_data = grupo_ref.to_dict()
            nombre_grupo = grupo_data.get('nombre', 'Grupo Desconocido')
        else:
            nombre_grupo = 'Grupo Desconocido'
        
        # Obtener rúbrica activa
        rubrica = get_rubrica_activa()
        
        if not rubrica:
            flash('No hay rúbrica activa configurada', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        # Verificar si ya existe una evaluación previa
        evaluacion_ref = db.collection('proyectos').document(grupo_id).collection('evaluaciones').document(juez_email).get()
        
        evaluacion_existente = None
        if evaluacion_ref.exists:
            evaluacion_existente = evaluacion_ref.to_dict()
            flash('Ya has evaluado este proyecto. Puedes modificar tu evaluación.', 'info')
        
        return render_template('formulario_evaluacion.html',
                             proyecto=proyecto_data,
                             nombre_grupo=nombre_grupo,
                             rubrica=rubrica,
                             evaluacion_existente=evaluacion_existente,
                             grupo_id=grupo_id,
                             tema=obtener_tema_actual())
    
    except Exception as e:
        print(f"❌ Error en mostrar_evaluacion: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al cargar el formulario de evaluación', 'danger')
        return redirect(url_for('juez_dashboard'))

@app.route('/juez/guardar-evaluacion', methods=['POST'])
@requires_auth('juez')
def guardar_evaluacion_juez():
    """Guarda la evaluación de un juez"""
    try:
        data = request.form
        grupo_id = data.get('grupo_id')
        juez_email = session.get('user_id')
        categoria_asignada = session.get('categoria_asignada')
        
        print(f"DEBUG: Guardando evaluación para grupo {grupo_id} por juez {juez_email}")
        
        # Verificar que el proyecto existe y es de la categoría correcta
        proyecto_ref = db.collection('proyectos').document(grupo_id).get()
        
        if not proyecto_ref.exists:
            flash('Proyecto no encontrado', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        proyecto_data = proyecto_ref.to_dict()
        
        if proyecto_data.get('categoria') != categoria_asignada:
            flash('No tienes permiso para evaluar este proyecto', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        # Obtener rúbrica activa
        rubrica = get_rubrica_activa()
        
        if not rubrica:
            flash('No hay rúbrica activa', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        # Procesar puntuaciones de cada criterio
        puntuaciones = {}
        puntaje_total_normalizado = 0.0
        
        for criterio_meta in rubrica['criterios']:
            criterio_nombre = criterio_meta['nombre']
            
            # Obtener puntaje ingresado por el juez
            try:
                puntaje_str = data.get(criterio_nombre, '0')
                puntaje_obtenido = float(puntaje_str)
            except ValueError:
                puntaje_obtenido = 0.0
            
            # Validar rango
            puntos_max = criterio_meta['puntos_maximos']
            if puntaje_obtenido < 0:
                puntaje_obtenido = 0.0
            elif puntaje_obtenido > puntos_max:
                puntaje_obtenido = puntos_max
            
            porcentaje = criterio_meta['porcentaje']
            
            # Calcular contribución ponderada
            contribucion = (puntaje_obtenido / puntos_max) * (porcentaje / 100)
            puntaje_total_normalizado += contribucion
            
            puntuaciones[criterio_nombre] = {
                'puntos_obtenidos': puntaje_obtenido,
                'puntos_maximos': puntos_max,
                'porcentaje_peso': porcentaje,
                'contribucion_normalizada': round(contribucion, 4)
            }
        
        # Convertir a porcentaje (0-100)
        puntaje_final_porcentaje = round(puntaje_total_normalizado * 100, 2)
        
        # Crear documento de evaluación
        evaluacion_data = {
            'juez_email': juez_email,
            'juez_nombre': session.get('user_name', 'Juez'),
            'fecha_evaluacion': firestore.SERVER_TIMESTAMP,
            'puntuacion_final': puntaje_final_porcentaje,
            'rubrica_id': rubrica['id'],
            'rubrica_nombre': rubrica['nombre'],
            'puntuaciones_criterios': puntuaciones,
            'comentarios': data.get('comentarios', ''),
            'categoria_proyecto': categoria_asignada
        }
        
        # Verificar si es actualización o creación
        evaluacion_ref = db.collection('proyectos').document(grupo_id).collection('evaluaciones').document(juez_email)
        evaluacion_existente = evaluacion_ref.get().exists
        
        # Guardar en Firestore
        evaluacion_ref.set(evaluacion_data)
        
        # Calcular y actualizar promedio del grupo
        promedio, _ = calcular_promedio_evaluaciones_dinamico(grupo_id)
        
        # Actualizar proyecto
        proyecto_ref = db.collection('proyectos').document(grupo_id)
        proyecto_ref.update({
            'promedio_evaluaciones': promedio,
            'ultima_evaluacion': firestore.SERVER_TIMESTAMP
        })
        
        if not evaluacion_existente:
            # Solo incrementar si es nueva evaluación
            proyecto_ref.update({
                'num_evaluaciones': firestore.Increment(1)
            })
        
        flash('✅ Evaluación guardada exitosamente', 'success')
        return redirect(url_for('juez_dashboard'))
    
    except Exception as e:
        print(f"❌ Error al guardar evaluación: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al guardar la evaluación', 'danger')
        return redirect(url_for('juez_dashboard'))

@app.route('/juez/ver-evaluacion/<grupo_id>')
@requires_auth('juez')
def ver_evaluacion(grupo_id):
    """Muestra los detalles de una evaluación ya guardada"""
    try:
        juez_email = session.get('user_id')
        
        # Obtener evaluación
        evaluacion_ref = db.collection('proyectos').document(grupo_id).collection('evaluaciones').document(juez_email).get()
        
        if not evaluacion_ref.exists:
            flash('Evaluación no encontrada', 'danger')
            return redirect(url_for('juez_dashboard'))
        
        evaluacion_data = evaluacion_ref.to_dict()
        
        # Obtener datos del proyecto
        proyecto_ref = db.collection('proyectos').document(grupo_id).get()
        proyecto_data = proyecto_ref.to_dict()
        proyecto_data['id'] = grupo_id
        
        # Obtener nombre del grupo
        grupo_ref = db.collection('grupos').document(grupo_id).get()
        if grupo_ref.exists:
            grupo_data = grupo_ref.to_dict()
            nombre_grupo = grupo_data.get('nombre', 'Grupo Desconocido')
        else:
            nombre_grupo = 'Grupo Desconocido'
        
        # Obtener promedio de todas las evaluaciones
        promedio, evaluaciones_list = calcular_promedio_evaluaciones_dinamico(grupo_id)
        
        # Obtener rúbrica para mostrar detalles
        rubrica_ref = db.collection('rubricas').document(evaluacion_data.get('rubrica_id')).get()
        rubrica_data = rubrica_ref.to_dict() if rubrica_ref.exists else None
        
        return render_template('ver_evaluacion.html',
                             evaluacion=evaluacion_data,
                             proyecto=proyecto_data,
                             nombre_grupo=nombre_grupo,
                             promedio_final=promedio,
                             todas_evaluaciones=evaluaciones_list,
                             rubrica=rubrica_data,
                             tema=obtener_tema_actual())
    
    except Exception as e:
        print(f"❌ Error al ver evaluación: {e}")
        flash('Error al cargar la evaluación', 'danger')
        return redirect(url_for('juez_dashboard'))

@app.route('/juez/obtener-rubrica-activa', methods=['GET'])
@requires_auth('juez')
def juez_obtener_rubrica_activa():
    """Obtiene la rúbrica activa para el juez"""
    rubrica_data = get_rubrica_activa()
    if rubrica_data:
        return jsonify({'success': True, 'rubrica': rubrica_data})
    else:
        return jsonify({'success': False, 'error': 'No hay rúbrica activa'})

# ==============================================================================
# RUTA DEL PARTICIPANTE DASHBOARD
# ==============================================================================

@app.route('/participante/dashboard')
@requires_auth('participante')
def participante_dashboard():
    try:
        participante_id = session.get('user_id')
        user_info = get_user_info(participante_id)
        grupo = None
        proyecto = None
        evaluaciones = []
        rubrica_activa = get_rubrica_activa()
        promedio_score = 0.0
        
        if db_connected():
            # 1. Encontrar el grupo del participante
            grupos_ref = db.collection('grupos').where('miembros', 'array_contains', participante_id).limit(1).stream()
            grupo_doc = next(grupos_ref, None)
            
            if grupo_doc:
                grupo = grupo_doc.to_dict()
                grupo_id = grupo_doc.id
                grupo['id'] = grupo_id
                grupo['es_lider'] = (grupo.get('lider_id') == participante_id)
                session['grupo_nombre'] = grupo.get('nombre', 'Sin nombre')
                
                # Obtener info de miembros
                miembros_info = []
                for miembro_id in grupo.get('miembros', []):
                    miembro_data = get_user_info(miembro_id)
                    miembros_info.append({
                        'id': miembro_id,
                        'nombre': miembro_data['user_name'],
                        'es_lider': (miembro_id == grupo.get('lider_id'))
                    })
                grupo['miembros'] = miembros_info
                
                # 2. Obtener el proyecto asociado
                proyecto_doc = db.collection('proyectos').document(grupo_id).get()
                if proyecto_doc.exists:
                    proyecto = proyecto_doc.to_dict()
                    proyecto['id'] = grupo_id
                    
                    # 3. Obtener y calcular el promedio de evaluaciones
                    promedio_score, evaluaciones = calcular_promedio_evaluaciones_dinamico(grupo_id)
                    proyecto['promedio_score'] = promedio_score
                    
                    # Agregar nombre del juez a cada evaluación
                    for eval_data in evaluaciones:
                        juez_email = eval_data.get('juez_email') or eval_data.get('juez_id')
                        if juez_email:
                            juez_info = get_user_info(juez_email)
                            eval_data['juez_nombre'] = juez_info['user_name']
                        else:
                            eval_data['juez_nombre'] = 'Juez Desconocido'

        return render_template('participante_dashboard.html',
                               user_name=user_info['user_name'],
                               grupo=grupo,
                               proyecto=proyecto,
                               evaluaciones=evaluaciones,
                               rubrica_activa=rubrica_activa,
                               tema=obtener_tema_actual())
    
    except Exception as e:
        print(f"Error al obtener información del participante: {e}")
        flash('Ocurrió un error al cargar tu información. Intenta más tarde.', 'error')
        return redirect(url_for('index'))

# ==============================================================================
# 5. RUTA: SUBIDA Y REGISTRO DE PROYECTO
# ==============================================================================

@app.route('/participante/registrar-proyecto', methods=['POST'])
@requires_auth('participante')
def registrar_proyecto():
    if not is_feria_abierta() and not is_ediciones_habilitadas():
        flash('La feria está cerrada. No se pueden registrar o editar proyectos.', 'error')
        return redirect(url_for('participante_dashboard'))
    
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('participante_dashboard'))

    participante_id = session.get('user_id')
    
    try:
        grupos_ref = db.collection('grupos').where('miembros', 'array_contains', participante_id).limit(1).stream()
        grupo_doc = next(grupos_ref, None)
        
        if not grupo_doc:
            flash('Debes pertenecer a un grupo para crear un proyecto.', 'error')
            return redirect(url_for('participante_dashboard'))
        
        grupo = grupo_doc.to_dict()
        grupo_id = grupo_doc.id
        
        if grupo.get('lider_id') != participante_id:
            flash('Solo el líder del grupo puede crear o editar el proyecto.', 'error')
            return redirect(url_for('participante_dashboard'))
        
    except Exception as e:
        print(f"Error al verificar grupo: {e}")
        flash('Error al verificar tu grupo.', 'error')
        return redirect(url_for('participante_dashboard'))
    
    titulo = request.form.get('titulo')
    categoria = request.form.get('categoria')
    resumen = request.form.get('resumen')
    archivo_proyecto = request.files.get('archivo_proyecto')
    imagen_proyecto = request.files.get('imagen_proyecto')

    if not all([titulo, categoria, resumen]):
        flash('Error: Todos los campos de texto son obligatorios.', 'error')
        return redirect(url_for('participante_dashboard'))

    try:
        archivo_url = ""
        imagen_url = ""
        
        if archivo_proyecto and archivo_proyecto.filename:
            print(f"Archivo subido simulado: {archivo_proyecto.filename}")
            safe_titulo = titulo.replace(' ', '_').lower()
            archivo_url = f"gs://tu-bucket-name/{grupo_id}/{safe_titulo}/{archivo_proyecto.filename}"
        
        if imagen_proyecto and imagen_proyecto.filename:
            print(f"Imagen subida simulada: {imagen_proyecto.filename}")
            safe_titulo = titulo.replace(' ', '_').lower()
            imagen_url = f"gs://tu-bucket-name/{grupo_id}/{safe_titulo}/{imagen_proyecto.filename}"

        proyecto_data = {
            'grupo_id': grupo_id,
            'lider_id': participante_id,
            'nombre_equipo': grupo['nombre'],
            'titulo': titulo,
            'categoria': categoria,
            'resumen': resumen,
            'archivo_url': archivo_url,
            'imagen_url': imagen_url,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP,
            'estado': 'Pendiente de Revisión'
        }
        
        doc_ref = db.collection('proyectos').document(grupo_id)
        doc_ref.set(proyecto_data, merge=True)
        
        grupo_ref = db.collection('grupos').document(grupo_id)
        grupo_ref.update({'categoria': categoria})

        flash('¡Proyecto registrado/actualizado exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al registrar proyecto: {e}")
        flash('Ocurrió un error al guardar los detalles del proyecto.', 'error')
        
    return redirect(url_for('participante_dashboard'))

# ==============================================================================
# 6. RUTAS DE GESTIÓN DE GRUPOS (PARTICIPANTES)
# ==============================================================================

@app.route('/participante/crear-grupo', methods=['POST'])
@requires_auth('participante')
def crear_grupo():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('participante_dashboard'))
    
    participante_id = session.get('user_id')
    nombre_grupo = request.form.get('nombre_grupo')
    
    if not nombre_grupo or nombre_grupo.strip() == '':
        flash('El nombre del grupo es obligatorio.', 'error')
        return redirect(url_for('participante_dashboard'))
    
    try:
        grupos_ref = db.collection('grupos').where('miembros', 'array_contains', participante_id).limit(1).stream()
        if any(grupos_ref):
            flash('Ya perteneces a un grupo. No puedes crear uno nuevo.', 'error')
            return redirect(url_for('participante_dashboard'))
        
        codigo_grupo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        while db.collection('grupos').where('codigo', '==', codigo_grupo).limit(1).get():
            codigo_grupo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        
        user_info = get_user_info(participante_id)
        
        grupo_data = {
            'nombre': nombre_grupo.strip(),
            'lider_id': participante_id,
            'lider_nombre': user_info['user_name'],
            'codigo': codigo_grupo,
            'miembros': [participante_id],
            'fecha_creacion': firestore.SERVER_TIMESTAMP,
            'categoria': None
        }
        
        grupo_ref = db.collection('grupos').document()
        grupo_ref.set(grupo_data)
        
        flash(f'¡Grupo "{nombre_grupo}" creado exitosamente! Tu código de invitación es: {codigo_grupo}', 'success')
        
    except Exception as e:
        print(f"Error al crear grupo: {e}")
        flash('Ocurrió un error al crear el grupo. Intenta nuevamente.', 'error')
    
    return redirect(url_for('participante_dashboard'))

@app.route('/participante/unirse-grupo', methods=['POST'])
@requires_auth('participante')
def unirse_grupo():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('participante_dashboard'))
    
    participante_id = session.get('user_id')
    codigo_grupo = request.form.get('codigo_grupo')
    
    if not codigo_grupo or codigo_grupo.strip() == '':
        flash('Debes ingresar un código de invitación.', 'error')
        return redirect(url_for('participante_dashboard'))
    
    codigo_grupo = codigo_grupo.strip().upper()
    
    try:
        grupos_ref = db.collection('grupos').where('miembros', 'array_contains', participante_id).limit(1).stream()
        if any(grupos_ref):
            flash('Ya perteneces a un grupo. No puedes unirte a otro.', 'error')
            return redirect(url_for('participante_dashboard'))
        
        grupos_query = db.collection('grupos').where('codigo', '==', codigo_grupo).limit(1).stream()
        grupo_doc = next(grupos_query, None)
        
        if not grupo_doc:
            flash('Código de invitación inválido. Verifica el código e intenta nuevamente.', 'error')
            return redirect(url_for('participante_dashboard'))
        
        grupo_data = grupo_doc.to_dict()
        grupo_ref = db.collection('grupos').document(grupo_doc.id)
        
        if len(grupo_data.get('miembros', [])) >= 5:
            flash('Este grupo ya tiene el máximo de 5 miembros.', 'error')
            return redirect(url_for('participante_dashboard'))
        
        grupo_ref.update({
            'miembros': firestore.ArrayUnion([participante_id])
        })
        
        flash(f'¡Te has unido exitosamente al grupo "{grupo_data["nombre"]}"!', 'success')
        
    except Exception as e:
        print(f"Error al unirse al grupo: {e}")
        flash('Ocurrió un error al intentar unirse al grupo. Intenta nuevamente.', 'error')
    
    return redirect(url_for('participante_dashboard'))

# ==============================================================================
# 7. RUTAS DE GESTIÓN DE JUECES (ADMIN)
# ==============================================================================

@app.route('/admin/crear-juez', methods=['POST'])
@requires_auth('admin')
def crear_juez():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    nombre = request.form.get('nombre_completo')
    correo = request.form.get('correo_institucional')
    password_temp = request.form.get('password_temporal')
    categoria_asignada = request.form.get('categoria_asignada')
    
    if not all([nombre, correo, password_temp, categoria_asignada]):
        flash('Todos los campos son obligatorios para crear el juez.', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        juez_id = correo 
        doc_ref = db.collection('usuarios').document(juez_id)
        
        if doc_ref.get().exists:
            flash(f'El correo {correo} ya se encuentra registrado.', 'error')
            return redirect(url_for('admin_dashboard'))

        password_hash = generate_password_hash(password_temp)
        
        juez_data = {
            'nombre': nombre,
            'correo': correo,
            'rol': 'juez',
            'categoria_asignada': categoria_asignada,
            'fecha_registro': firestore.SERVER_TIMESTAMP,
            'password_hash': password_hash
        }
        
        doc_ref.set(juez_data)
        
        flash(f'¡Juez {nombre} creado exitosamente! Categoría: {categoria_asignada}', 'success')
        
    except Exception as e:
        print(f"Error al crear juez: {e}")
        flash('Ocurrió un error al registrar el nuevo juez.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/editar-juez', methods=['POST'])
@requires_auth('admin')
def editar_juez():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    juez_id = request.form.get('juez_id')
    nombre = request.form.get('nombre_completo')
    password_nueva = request.form.get('password_nueva')
    categoria_asignada = request.form.get('categoria_asignada')
    
    if not all([juez_id, nombre, categoria_asignada]):
        flash('Faltan datos para actualizar el juez.', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        doc_ref = db.collection('usuarios').document(juez_id)
        
        if not doc_ref.get().exists:
            flash(f'El juez con correo {juez_id} no existe.', 'error')
            return redirect(url_for('admin_dashboard'))

        update_data = {
            'nombre': nombre,
            'categoria_asignada': categoria_asignada,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP
        }
        
        if password_nueva and len(password_nueva) >= 6:
            update_data['password_hash'] = generate_password_hash(password_nueva)
        
        doc_ref.update(update_data)
        
        flash(f'¡Juez {nombre} actualizado exitosamente! Categoría: {categoria_asignada}', 'success')
        
    except Exception as e:
        print(f"Error al editar juez: {e}")
        flash('Ocurrió un error al actualizar el juez.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/eliminar-juez', methods=['POST'])
@requires_auth('admin')
def eliminar_juez():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    juez_id = request.form.get('juez_id')
    
    if not juez_id:
        flash('Falta el ID del juez a eliminar.', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        doc_ref = db.collection('usuarios').document(juez_id)
        
        if not doc_ref.get().exists:
            flash(f'El juez con correo {juez_id} no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        doc_ref.delete()
        
        flash(f'¡Juez eliminado exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al eliminar juez: {e}")
        flash('Ocurrió un error al eliminar el juez.', 'error')
        
    return redirect(url_for('admin_dashboard'))

# ==============================================================================
# 8. RUTAS PARA ESTUDIANTES
# ==============================================================================

@app.route('/admin/crear-estudiante', methods=['POST'])
@requires_auth('admin')
def crear_estudiante():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    nombre = request.form.get('nombre')
    apellido = request.form.get('apellido')
    correo = request.form.get('correo')
    password = request.form.get('password')
    ciclo = request.form.get('ciclo')
    grupo_id = request.form.get('grupo_id')
    
    if not all([nombre, apellido, correo, password, ciclo]):
        flash('Todos los campos obligatorios deben estar llenos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    if len(password) < 6:
        flash("La contraseña debe tener al menos 6 caracteres.", 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        # Verificar si el correo ya existe
        doc_ref = db.collection('usuarios').document(correo)
        if doc_ref.get().exists:
            flash('El correo electrónico ya se encuentra registrado.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        password_hash = generate_password_hash(password)
        
        estudiante_data = {
            'nombre': nombre,
            'apellido': apellido,
            'correo': correo,
            'cuenta': correo,
            'ciclo': ciclo,
            'rol': 'participante',
            'fecha_registro': firestore.SERVER_TIMESTAMP,
            'password_hash': password_hash,
            'grupo_asignado': grupo_id if grupo_id else None
        }
        
        doc_ref.set(estudiante_data)
        
        if grupo_id:
            grupo_ref = db.collection('grupos').document(grupo_id)
            grupo_ref.update({
                'miembros': firestore.ArrayUnion([correo])
            })
        
        flash(f'¡Estudiante {nombre} {apellido} creado exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al crear estudiante: {e}")
        flash('Ocurrió un error al crear el estudiante.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/asignar-grupo-estudiante', methods=['POST'])
@requires_auth('admin')
def asignar_grupo_estudiante():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    estudiante_id = request.form.get('estudiante_id')
    grupo_id = request.form.get('grupo_id')
    
    if not all([estudiante_id, grupo_id]):
        flash('Faltan datos para asignar el grupo.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        estudiante_ref = db.collection('usuarios').document(estudiante_id)
        estudiante_doc = estudiante_ref.get()
        if not estudiante_doc.exists:
            flash('El estudiante especificado no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        grupo_ref = db.collection('grupos').document(grupo_id)
        grupo_doc = grupo_ref.get()
        if not grupo_doc.exists:
            flash('El grupo especificado no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        grupo_data = grupo_doc.to_dict()
        
        estudiante_ref.update({
            'grupo_asignado': grupo_id,
            'grupo_nombre': grupo_data.get('nombre', 'Sin nombre')
        })
        
        if estudiante_id not in grupo_data.get('miembros', []):
            grupo_ref.update({
                'miembros': firestore.ArrayUnion([estudiante_id])
            })
        
        flash('¡Estudiante asignado al grupo exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al asignar grupo: {e}")
        flash('Ocurrió un error al asignar el grupo.', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/obtener-info-estudiante/<estudiante_id>')
@requires_auth('admin')
def obtener_info_estudiante(estudiante_id):
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'})
    
    try:
        estudiante_doc = db.collection('usuarios').document(estudiante_id).get()
        if not estudiante_doc.exists:
            return jsonify({'success': False, 'error': 'Estudiante no encontrado'})
        
        estudiante_data = estudiante_doc.to_dict()
        
        grupo_info = None
        grupo_id = estudiante_data.get('grupo_asignado')
        if grupo_id:
            grupo_doc = db.collection('grupos').document(grupo_id).get()
            if grupo_doc.exists:
                grupo_data = grupo_doc.to_dict()
                grupo_info = {
                    'id': grupo_id,
                    'nombre': grupo_data.get('nombre'),
                    'codigo': grupo_data.get('codigo'),
                    'categoria': grupo_data.get('categoria')
                }
        
        fecha_registro = estudiante_data.get('fecha_registro')
        if fecha_registro and hasattr(fecha_registro, 'strftime'):
            fecha_str = fecha_registro.strftime('%d/%m/%Y')
        else:
            fecha_str = 'N/A'
        
        return jsonify({
            'success': True,
            'estudiante': {
                'id': estudiante_id,
                'nombre': estudiante_data.get('nombre'),
                'apellido': estudiante_data.get('apellido'),
                'correo': estudiante_data.get('correo') or estudiante_data.get('cuenta'),
                'ciclo': estudiante_data.get('ciclo'),
                'grupo': grupo_info,
                'fecha_registro': fecha_str
            }
        })
        
    except Exception as e:
        print(f"Error al obtener información del estudiante: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/eliminar-estudiante', methods=['POST'])
@requires_auth('admin')
def eliminar_estudiante():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    estudiante_id = request.form.get('estudiante_id')
    
    if not estudiante_id:
        flash('Falta el ID del estudiante a eliminar.', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        doc_ref = db.collection('usuarios').document(estudiante_id)
        
        if not doc_ref.get().exists:
            flash(f'El estudiante no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        doc_ref.delete()
        
        flash(f'¡Estudiante eliminado exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al eliminar estudiante: {e}")
        flash('Ocurrió un error al eliminar el estudiante.', 'error')
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/crear-grupo', methods=['POST'])
@requires_auth('admin')
def admin_crear_grupo():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    nombre_grupo = request.form.get('nombre_grupo')
    categoria_grupo = request.form.get('categoria_grupo')
    
    if not nombre_grupo or nombre_grupo.strip() == '':
        flash('El nombre del grupo es obligatorio.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        codigo_grupo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        
        while True:
            grupos_query = db.collection('grupos').where('codigo', '==', codigo_grupo).limit(1).stream()
            if not any(grupos_query):
                break
            codigo_grupo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=9))
        
        grupo_data = {
            'nombre': nombre_grupo.strip(),
            'lider_id': None,
            'lider_nombre': 'Por asignar',
            'codigo': codigo_grupo,
            'miembros': [],
            'fecha_creacion': firestore.SERVER_TIMESTAMP,
            'categoria': categoria_grupo if categoria_grupo else None
        }
        
        grupo_ref = db.collection('grupos').document()
        grupo_ref.set(grupo_data)
        
        flash(f'¡Grupo "{nombre_grupo}" creado exitosamente! Código: {codigo_grupo}', 'success')
        
    except Exception as e:
        print(f"Error al crear grupo desde admin: {e}")
        flash('Ocurrió un error al crear el grupo. Intenta nuevamente.', 'error')
    
    return redirect(url_for('admin_dashboard'))

# ==============================================================================
# 9. RUTAS DE ASIGNACIÓN Y CONFIGURACIÓN (ADMIN)
# ==============================================================================

@app.route('/admin/asignar-juez', methods=['POST'])
@requires_auth('admin')
def asignar_juez():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    proyecto_id = request.form.get('proyecto_id')
    juez_id = request.form.get('juez_id')
    
    if not all([proyecto_id, juez_id]):
        flash('Faltan datos para asignar el juez.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        proyecto_ref = db.collection('proyectos').document(proyecto_id)
        
        if not proyecto_ref.get().exists:
            flash('El proyecto especificado no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        proyecto_ref.update({'juez_asignado': juez_id})
        
        flash('¡Juez asignado exitosamente al proyecto!', 'success')
        
    except Exception as e:
        print(f"Error al asignar juez: {e}")
        flash('Ocurrió un error al asignar el juez.', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle-feria', methods=['POST'])
@requires_auth('admin')
def toggle_feria_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        data = request.get_json()
        feria_abierta = data.get('feria_abierta', False)
        
        config_ref = db.collection('configuracion').document('feria')
        config_ref.set({
            'feria_abierta': feria_abierta,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP,
            'actualizado_por': session.get('user_id')
        }, merge=True)
        
        estado = "abierta" if feria_abierta else "cerrada"
        return jsonify({'success': True, 'message': f'Feria {estado} correctamente'})
    
    except Exception as e:
        print(f"Error al cambiar estado de feria: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/toggle-ediciones', methods=['POST'])
@requires_auth('admin')
def toggle_ediciones_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        data = request.get_json()
        ediciones_habilitadas = data.get('ediciones_habilitadas', False)
        
        config_ref = db.collection('configuracion').document('feria')
        config_ref.set({
            'ediciones_habilitadas': ediciones_habilitadas,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP,
            'actualizado_por': session.get('user_id')
        }, merge=True)
        
        estado = "habilitadas" if ediciones_habilitadas else "deshabilitadas"
        return jsonify({'success': True, 'message': f'Ediciones {estado} correctamente'})
    
    except Exception as e:
        print(f"Error al cambiar ediciones: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/actualizar-fecha-evento', methods=['POST'])
@requires_auth('admin')
def actualizar_fecha_evento_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        data = request.get_json()
        fecha_evento = data.get('fecha_evento')
        
        if not fecha_evento:
            return jsonify({'success': False, 'error': 'Falta la fecha del evento'}), 400
        
        try:
            datetime.fromisoformat(fecha_evento)
        except:
            return jsonify({'success': False, 'error': 'Formato de fecha inválido'}), 400
        
        config_ref = db.collection('configuracion').document('feria')
        config_ref.set({
            'fecha_evento': fecha_evento,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP,
            'actualizado_por': session.get('user_id')
        }, merge=True)
        
        return jsonify({'success': True, 'message': 'Fecha actualizada correctamente'})
    
    except Exception as e:
        print(f"Error al actualizar fecha: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/actualizar-info-feria', methods=['POST'])
@requires_auth('admin')
def actualizar_info_feria_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        año = data.get('año')
        descripcion = data.get('descripcion')
        tema = data.get('tema', 'claro')
        
        if not all([nombre, año]):
            return jsonify({'success': False, 'error': 'Faltan datos obligatorios'}), 400
        
        config_ref = db.collection('configuracion').document('feria')
        config_ref.set({
            'nombre': nombre,
            'año': año,
            'descripcion': descripcion,
            'tema': tema,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP,
            'actualizado_por': session.get('user_id')
        }, merge=True)
        
        return jsonify({'success': True, 'message': 'Información actualizada correctamente'})
    
    except Exception as e:
        print(f"Error al actualizar información: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/obtener-config-feria', methods=['GET'])
@requires_auth('admin')
def obtener_config_feria_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        config_doc = db.collection('configuracion').document('feria').get()
        if config_doc.exists:
            config_data = config_doc.to_dict()
            if 'tema' not in config_data:
                config_data['tema'] = 'claro'
            if 'fecha_evento' not in config_data:
                config_data['fecha_evento'] = '2025-12-05'
            if 'feria_abierta' not in config_data:
                config_data['feria_abierta'] = False
            if 'ediciones_habilitadas' not in config_data:
                config_data['ediciones_habilitadas'] = False
            return jsonify({'success': True, 'config': config_data})
        else:
            return jsonify({'success': True, 'config': {
                'feria_abierta': False,
                'ediciones_habilitadas': False,
                'nombre': 'Feria de Logros UGB',
                'año': 2025,
                'descripcion': 'Feria anual de proyectos tecnológicos',
                'fecha_evento': '2025-12-05',
                'tema': 'claro'
            }})
    except Exception as e:
        print(f"Error al obtener configuración: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/crear-respaldo', methods=['POST'])
@requires_auth('admin')
def crear_respaldo_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        return jsonify({'success': True, 'message': 'Respaldo creado exitosamente'})
    except Exception as e:
        print(f"Error al crear respaldo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==============================================================================
# 11. RUTAS DE GESTIÓN DE GRUPOS (ADMIN)
# ==============================================================================

@app.route('/admin/editar-grupo', methods=['POST'])
@requires_auth('admin')
def editar_grupo_admin():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    grupo_id = request.form.get('grupo_id')
    nombre = request.form.get('nombre')
    
    if not all([grupo_id, nombre]):
        flash('Faltan datos para actualizar el grupo.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        grupo_ref = db.collection('grupos').document(grupo_id)
        
        if not grupo_ref.get().exists:
            flash('El grupo especificado no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        grupo_ref.update({'nombre': nombre})
        
        flash('¡Grupo actualizado exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al editar grupo: {e}")
        flash('Ocurrió un error al actualizar el grupo.', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/eliminar-grupo', methods=['POST'])
@requires_auth('admin')
def eliminar_grupo_admin():
    if not db_connected():
        flash('Error de conexión a la base de datos.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    grupo_id = request.form.get('grupo_id')
    
    if not grupo_id:
        flash('Falta el ID del grupo a eliminar.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    try:
        grupo_ref = db.collection('grupos').document(grupo_id)
        
        if not grupo_ref.get().exists:
            flash('El grupo especificado no existe.', 'error')
            return redirect(url_for('admin_dashboard'))
        
        proyecto_ref = db.collection('proyectos').document(grupo_id)
        if proyecto_ref.get().exists:
            proyecto_ref.delete()
        
        grupo_ref.delete()
        
        flash('¡Grupo y proyecto asociado eliminados exitosamente!', 'success')
        
    except Exception as e:
        print(f"Error al eliminar grupo: {e}")
        flash('Ocurrió un error al eliminar el grupo.', 'error')
    
    return redirect(url_for('admin_dashboard'))

# ==============================================================================
# 12. RUTAS DE PERFIL Y CONTRASEÑA
# ==============================================================================

@app.route('/actualizar_perfil', methods=['POST'])
@requires_auth('admin')
def actualizar_perfil_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        data = request.get_json()
        nombre = data.get('nombre')
        
        if not nombre:
            return jsonify({'success': False, 'error': 'El nombre es obligatorio'}), 400
        
        user_id = session.get('user_id')
        doc_ref = db.collection('usuarios').document(user_id)
        
        update_data = {
            'nombre': nombre,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP
        }
        
        doc_ref.update(update_data)
        
        session['user_name'] = nombre
        
        return jsonify({'success': True, 'message': 'Perfil actualizado correctamente'})
    
    except Exception as e:
        print(f"Error al actualizar perfil: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/cambiar_contrasena', methods=['POST'])
@requires_auth('admin')
def cambiar_contrasena_route():
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        data = request.get_json()
        password_actual = data.get('password_actual')
        password_nueva = data.get('password_nueva')
        
        if not all([password_actual, password_nueva]):
            return jsonify({'success': False, 'error': 'Todos los campos son obligatorios'}), 400
        
        if len(password_nueva) < 6:
            return jsonify({'success': False, 'error': 'La nueva contraseña debe tener al menos 6 caracteres'}), 400
        
        user_id = session.get('user_id')
        doc_ref = db.collection('usuarios').document(user_id)
        user_doc = doc_ref.get()
        
        if not user_doc.exists:
            return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404
        
        user_data = user_doc.to_dict()
        stored_hash = user_data.get('password_hash')
        
        if not check_password_hash(stored_hash, password_actual):
            return jsonify({'success': False, 'error': 'La contraseña actual es incorrecta'}), 400
        
        new_hash = generate_password_hash(password_nueva)
        doc_ref.update({
            'password_hash': new_hash,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP
        })
        
        return jsonify({'success': True, 'message': 'Contraseña actualizada correctamente'})
    
    except Exception as e:
        print(f"Error al cambiar contraseña: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==============================================================================
# 13. RUTA DE LOGOUT
# ==============================================================================

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('index'))

@app.route('/limpiar-flag-login', methods=['POST'])
def limpiar_flag_login():
    """Limpia el flag just_logged_in después de mostrar el toast"""
    if 'just_logged_in' in session:
        session.pop('just_logged_in')
    return jsonify({'success': True})

# ==============================================================================
# 14. RUTAS DE EDICIÓN DE ESTUDIANTE
# ==============================================================================

@app.route('/admin/editar-estudiante-info', methods=['POST'])
@requires_auth('admin')
def editar_estudiante_info():
    """Ruta para editar información completa del estudiante incluyendo grupo"""
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        estudiante_id = request.form.get('estudiante_id')
        nombre = request.form.get('nombre')
        apellido = request.form.get('apellido')
        ciclo = request.form.get('ciclo')
        grupo_id = request.form.get('grupo_id')
        password_nueva = request.form.get('password_nueva')
        
        if not all([estudiante_id, nombre, apellido, ciclo]):
            flash('Faltan datos obligatorios', 'error')
            return redirect(url_for('admin_dashboard', seccion_activa='estudiantes'))
        
        doc_ref = db.collection('usuarios').document(estudiante_id)
        
        if not doc_ref.get().exists:
            flash('El estudiante no existe', 'error')
            return redirect(url_for('admin_dashboard', seccion_activa='estudiantes'))
        
        update_data = {
            'nombre': nombre,
            'apellido': apellido,
            'ciclo': ciclo,
            'fecha_actualizacion': firestore.SERVER_TIMESTAMP
        }
        
        if password_nueva and len(password_nueva) >= 6:
            update_data['password_hash'] = generate_password_hash(password_nueva)
        
        try:
            grupos_ref = db.collection('grupos').where('miembros', 'array_contains', estudiante_id).stream()
            for grupo_doc in grupos_ref:
                db.collection('grupos').document(grupo_doc.id).update({
                    'miembros': firestore.ArrayRemove([estudiante_id])
                })
        except Exception as e:
            print(f"⚠️ Error al remover estudiante de grupos: {e}")

        if grupo_id:
            update_data['grupo_asignado'] = grupo_id
            
            try:
                grupo_ref = db.collection('grupos').document(grupo_id)
                grupo_ref.update({
                    'miembros': firestore.ArrayUnion([estudiante_id])
                })
            except Exception as e:
                print(f"⚠️ Error al agregar estudiante al array de miembros: {e}")
        else:
            update_data['grupo_asignado'] = None
        
        doc_ref.update(update_data)
        
        flash('¡Estudiante actualizado exitosamente!', 'success')
        return redirect(url_for('admin_dashboard', seccion_activa='estudiantes'))
        
    except Exception as e:
        print(f"Error al editar estudiante: {e}")
        flash('Ocurrió un error al actualizar el estudiante', 'error')
        return redirect(url_for('admin_dashboard'))
    
# ==============================================================================
# RUTAS DE RÚBRICAS
# ==============================================================================

@app.route('/admin/crear-rubrica', methods=['POST'])
@requires_auth('admin')
def crear_rubrica():
    """Crea una nueva rúbrica de evaluación"""
    if not db_connected():
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500
    
    try:
        nombre = request.form.get('nombre_rubrica')
        anio = request.form.get('anio')
        
        if not all([nombre, anio]):
            flash('El nombre y año son obligatorios', 'error')
            return redirect(url_for('admin_dashboard', seccion_activa='evaluaciones'))
        
        criterios = []
        criterios_keys = [key for key in request.form.keys() if key.startswith('criterios[')]
        
        indices_criterios = set()
        for key in criterios_keys:
            indice = key.split('[')[1].split(']')[0]
            indices_criterios.add(indice)
        
        for indice in sorted(indices_criterios):
            nombre_criterio = request.form.get(f'criterios[{indice}][nombre]')
            porcentaje = request.form.get(f'criterios[{indice}][porcentaje]')
            puntos_max = request.form.get(f'criterios[{indice}][puntos_max]')
            descripcion = request.form.get(f'criterios[{indice}][descripcion]', '')
            
            if nombre_criterio and porcentaje and puntos_max:
                criterios.append({
                    'nombre': nombre_criterio,
                    'porcentaje': float(porcentaje),
                    'puntos_maximos': int(puntos_max),
                    'descripcion': descripcion
                })
        
        if not criterios:
            flash('Debe agregar al menos un criterio', 'error')
            return redirect(url_for('admin_dashboard', seccion_activa='evaluaciones'))
        
        total_porcentaje = sum(c['porcentaje'] for c in criterios)
        if round(total_porcentaje) != 100:
            flash(f'Los porcentajes deben sumar 100%. Actualmente suman {total_porcentaje}%', 'error')
            return redirect(url_for('admin_dashboard', seccion_activa='evaluaciones'))
        
        rubrica_data = {
            'nombre': nombre,
            'anio': int(anio),
            'criterios': criterios,
            'activa': True,
            'fecha_creacion': firestore.SERVER_TIMESTAMP,
            'creado_por': session.get('user_id')
        }
        
        rubricas_ref = db.collection('rubricas').where('activa', '==', True).stream()
        for rubrica_doc in rubricas_ref:
            db.collection('rubricas').document(rubrica_doc.id).update({'activa': False})
        
        db.collection('rubricas').add(rubrica_data)
        
        flash(f'¡Rúbrica "{nombre}" creada exitosamente con {len(criterios)} criterios!', 'success')
        return redirect(url_for('admin_dashboard', seccion_activa='evaluaciones'))
        
    except Exception as e:
        print(f"Error al crear rúbrica: {e}")
        flash('Ocurrió un error al crear la rúbrica', 'error')
        return redirect(url_for('admin_dashboard', seccion_activa='evaluaciones'))

@app.route('/admin/obtener-rubrica-activa', methods=['GET'])
@requires_auth('admin')
def obtener_rubrica_activa_route():
    """Obtiene la rúbrica activa"""
    rubrica_data = get_rubrica_activa()
    if rubrica_data:
        return jsonify({'success': True, 'rubrica': rubrica_data})
    else:
        return jsonify({'success': False, 'error': 'No hay rúbrica activa'})

@app.route('/participante/obtener-rubrica-activa', methods=['GET'])
@requires_auth('participante')
def participante_obtener_rubrica_activa():
    """Obtiene la rúbrica activa para mostrar a los participantes"""
    rubrica_data = get_rubrica_activa()
    if rubrica_data:
        return jsonify({'success': True, 'rubrica': rubrica_data})
    else:
        return jsonify({'success': False, 'error': 'No hay rúbrica activa'})

# ==============================================================================
# 15. RUTA DE GUARDAR EVALUACIÓN (MANTENER COMPATIBILIDAD)
# ==============================================================================

@app.route('/juez/guardar_evaluacion', methods=['POST'])
@requires_auth('juez')
def guardar_evaluacion():
    """Mantener compatibilidad con formularios antiguos"""
    return guardar_evaluacion_juez()

# ==============================================================================
# 16. EJECUCIÓN PRINCIPAL
# ==============================================================================

# ==============================================================================
# FILTROS PERSONALIZADOS JINJA2
# ==============================================================================
@app.template_filter('zfill')
def zfill_filter(value, width=3):
    """Filtro para rellenar con ceros a la izquierda"""
    try:
        return str(value).zfill(width)
    except:
        return str(value)
    
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)