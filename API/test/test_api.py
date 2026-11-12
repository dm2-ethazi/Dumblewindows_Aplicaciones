import importlib
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.import_directory = tempfile.TemporaryDirectory()
        drivers = {name: MagicMock() for name in ('jpype', 'jaydebeapi', 'oracledb')}
        drivers['jpype'].isJVMStarted.return_value = True
        for name in ('jaydebeapi', 'oracledb'):
            drivers[name].connect.side_effect = AssertionError('Conexion externa no permitida')
        with patch.dict(sys.modules, drivers), patch.dict(os.environ, {
            'MARIADB_URL': 'sqlite://',
            'CACHE_PATH': str(Path(cls.import_directory.name) / 'cache.sqlite3'),
            'HISTORY_CSV_DIR': cls.import_directory.name,
        }):
            cls.api = importlib.import_module('app.main')
            cls.mariadb = importlib.import_module('app.db.mariadb')
            cls.sqlite = importlib.import_module('app.db.sqlite')
            cls.history = importlib.import_module('app.services.history')
            cls.enrollments = importlib.import_module('app.services.enrollments')
            cls.schemas = importlib.import_module('app.models.schemas')

    @classmethod
    def tearDownClass(cls):
        cls.mariadb.engine.dispose()
        cls.import_directory.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        database_path = Path(self.directory.name) / 'enrollments.sqlite3'
        self.engine = create_engine(f'sqlite:///{database_path.as_posix()}', connect_args={'check_same_thread': False})
        self.addCleanup(self.engine.dispose)
        self.mariadb.Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)

        @contextmanager
        def identity_session():
            with self.session.begin() as session:
                yield session

        @contextmanager
        def source_connection(kind):
            connection = MagicMock()
            connection.cursor.return_value.fetchall.return_value = []
            yield connection

        replacements = [
            (self.mariadb, 'engine', self.engine),
            (self.mariadb, 'Session', self.session),
            (self.mariadb, 'identity_session', identity_session),
            (self.sqlite, 'CACHE_PATH', Path(self.directory.name) / 'cache.sqlite3'),
            (self.history, 'CSV_DIR', Path(self.directory.name)),
            (self.history, 'source_connection', source_connection),
            (self.history, 'find_history', MagicMock(return_value=[])),
            (self.history, 'query_history', MagicMock(return_value=None)),
            (self.history, 'query_history_by_base', MagicMock(return_value=[])),
        ]
        for module, name, value in replacements:
            patcher = patch.object(module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        environment = patch.dict(os.environ, {'API_ACCESS_KEY': 'clave-ficticia-solo-test'})
        environment.start()
        self.addCleanup(environment.stop)
        self.client = TestClient(self.api.app)
        self.addCleanup(self.client.close)
        self.headers = {'X-API-Key': 'clave-ficticia-solo-test'}
        self.payload = {'full_name': 'Ana', 'apellido': 'Lopez Garcia'}

    def create_student(self, **changes):
        response = self.client.post('/matriculas', headers=self.headers, json={**self.payload, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_salud_publica(self):
        response = self.client.get('/salud')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 'R01')

    def test_rutas_protegidas_sin_clave(self):
        for method, path in [('GET', '/estudiantes'), ('GET', '/estudiantes/CE-ANA-LOP'),
                             ('POST', '/matriculas'), ('PUT', '/matriculas/CE-ANA-LOP'),
                             ('DELETE', '/matriculas/CE-ANA-LOP')]:
            with self.subTest(method=method, path=path):
                response = self.client.request(method, path, json=self.payload)
                self.assertEqual(response.status_code, 401)

    def test_clave_incorrecta(self):
        response = self.client.get('/estudiantes', headers={'X-API-Key': 'incorrecta'})
        self.assertEqual(response.status_code, 401)

    def test_clave_no_configurada(self):
        with patch.dict(os.environ, {'API_ACCESS_KEY': ''}):
            response = self.client.get('/estudiantes', headers=self.headers)
        self.assertEqual(response.status_code, 401)

    def test_listado_vacio(self):
        response = self.client.get('/estudiantes', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_limites_invalidos(self):
        for limit in (0, 101, 'abc'):
            with self.subTest(limit=limit):
                response = self.client.get('/estudiantes', params={'limit': limit}, headers=self.headers)
                self.assertEqual(response.status_code, 422)

    def test_crear_genera_id_e_ignora_id_cliente(self):
        student = self.create_student(student_id='NO-USAR')
        self.assertEqual(student['student_id'], 'CE-ANA-LOP')
        self.assertEqual(student['house'], 'Central')

    def test_alta_guarda_en_sqlite_antes_de_mariadb(self):
        student = self.create_student()
        local = self.sqlite.enrollment(student['student_id'])
        self.assertIsNotNone(local)
        self.assertEqual(local['full_name'], 'Ana')
        self.assertEqual(local['synced'], 1)
        self.assertEqual(local['mariadb_id'], student['id'])

    def test_pendiente_se_replica_al_arrancar(self):
        self.sqlite.save_enrollment({
            'student_id': 'CE-LUI-PER', 'full_name': 'Luis', 'apellido': 'Perez',
            'house': 'Central', 'birth_date': None,
        })
        self.assertEqual([row['student_id'] for row in self.sqlite.pending()], ['CE-LUI-PER'])
        self.enrollments.push_pending()
        self.assertEqual(self.sqlite.pending(), [])
        detail = self.client.get('/estudiantes/CE-LUI-PER', headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['nombre'], 'Luis')

    def test_identificadores_repetidos(self):
        first = self.create_student()
        second = self.create_student()
        self.assertEqual(first['student_id'], 'CE-ANA-LOP')
        self.assertEqual(second['student_id'], 'CE-ANA-LOP-02')

    def test_validacion_nombres(self):
        for name in ('   ', '12345', 'unknown person'):
            with self.subTest(name=name):
                response = self.client.post('/matriculas', headers=self.headers, json={**self.payload, 'full_name': name})
                self.assertEqual(response.status_code, 422)

    def test_fecha_invalida(self):
        response = self.client.post('/matriculas', headers=self.headers, json={**self.payload, 'birth_date': '2026-02-31'})
        self.assertEqual(response.status_code, 422)

    def test_consultar_matricula_por_id(self):
        student = self.create_student()
        response = self.client.get('/estudiantes/' + student['student_id'], headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['nombre'], 'Ana')
        self.assertEqual(response.json()['origen'], 'mariadb')

    def test_busqueda_por_nombre_y_casa(self):
        self.create_student()
        self.create_student(full_name='Luis')
        response = self.client.get('/estudiantes', params={'name': 'Ana', 'house': 'Central'}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([student['nombre'] for student in response.json()], ['Ana'])

    def test_consulta_base_devuelve_variantes(self):
        self.create_student()
        self.create_student()
        response = self.client.get('/estudiantes/CE-ANA-LOP', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)

    def test_actualizar_matricula(self):
        student = self.create_student()
        payload = {**self.payload, 'full_name': 'Elena', 'house': 'Central'}
        response = self.client.put('/matriculas/' + student['student_id'], headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['student_id'], 'CE-ELE-LOP')
        self.assertIsNotNone(self.sqlite.enrollment('CE-ELE-LOP'))
        self.assertIsNone(self.sqlite.enrollment(student['student_id']))

    def test_eliminar_matricula(self):
        student = self.create_student()
        path = '/matriculas/' + student['student_id']
        self.assertEqual(self.client.delete(path, headers=self.headers).status_code, 200)
        self.assertEqual(self.client.delete(path, headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get('/estudiantes/' + student['student_id'], headers=self.headers).status_code, 404)

    def test_modificar_inexistente(self):
        response = self.client.put('/matriculas/NO-EXI-STE', headers=self.headers, json={**self.payload, 'house': 'Central'})
        self.assertEqual(response.status_code, 404)

    def test_historicos_sin_duplicar_matricula(self):
        student = self.create_student()
        self.history.find_history.return_value = [self.schemas.StudentOut(
            id=student['student_id'], nombre='Otro', apellido='Historico', casa='Central', origen='derby')]
        response = self.client.get('/estudiantes', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['origen'], 'mariadb')

    def test_cache_temporal(self):
        self.assertIsNone(self.sqlite.cached('prueba'))
        self.sqlite.cache('prueba', {'nombre': 'Ana'})
        self.assertEqual(self.sqlite.cached('prueba'), {'nombre': 'Ana'})
        with self.sqlite.connection() as database:
            expired = (datetime.utcnow() - self.sqlite.CACHE_TTL - timedelta(seconds=1)).isoformat()
            database.execute('UPDATE student_cache SET cached_at=? WHERE cache_key=?', (expired, 'prueba'))
        self.assertIsNone(self.sqlite.cached('prueba'))

    def test_alias_en_ingles(self):
        response = self.client.get('/students', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_openapi_publico(self):
        response = self.client.get('/openapi.json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('/matriculas', response.json()['paths'])
        self.assertNotIn('/enrollments', response.json()['paths'])

    def test_consulta_devuelve_fecha_nacimiento(self):
        student = self.client.post('/matriculas', headers=self.headers, json={**self.payload, 'birth_date': '2001-03-14'}).json()
        detail = self.client.get('/estudiantes/' + student['student_id'], headers=self.headers).json()
        detail = detail[0] if isinstance(detail, list) else detail
        self.assertEqual(detail['nacimiento'], '2001-03-14')
        self.assertEqual(detail['fecha_nacimiento'], '2001-03-14')
        found = self.client.get('/estudiantes', headers=self.headers, params={'name': 'Ana'}).json()
        self.assertIn('2001-03-14', [item['nacimiento'] for item in found])


if __name__ == '__main__':
    unittest.main(verbosity=2)
