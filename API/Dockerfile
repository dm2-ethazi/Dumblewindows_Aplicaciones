FROM eclipse-temurin:21-jre-jammy AS jre
FROM python:3.12-slim
COPY --from=jre /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /opt/jdbc
RUN python - <<'PY'
import urllib.request
urls = {
    'derby.jar': 'https://repo1.maven.org/maven2/org/apache/derby/derby/10.17.1.0/derby-10.17.1.0.jar',
    'derbynet.jar': 'https://repo1.maven.org/maven2/org/apache/derby/derbynet/10.17.1.0/derbynet-10.17.1.0.jar',
    'derbyshared.jar': 'https://repo1.maven.org/maven2/org/apache/derby/derbyshared/10.17.1.0/derbyshared-10.17.1.0.jar',
    'derbyclient.jar': 'https://repo1.maven.org/maven2/org/apache/derby/derbyclient/10.17.1.0/derbyclient-10.17.1.0.jar',
    'derbytools.jar': 'https://repo1.maven.org/maven2/org/apache/derby/derbytools/10.17.1.0/derbytools-10.17.1.0.jar',
    'hsqldb.jar': 'https://repo1.maven.org/maven2/org/hsqldb/hsqldb/2.7.4/hsqldb-2.7.4.jar',
    'h2.jar': 'https://repo1.maven.org/maven2/com/h2database/h2/2.3.232/h2-2.3.232.jar',
}
for name, url in urls.items():
    urllib.request.urlretrieve(url, '/opt/jdbc/' + name)
PY
COPY app ./app
COPY data ./data
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
