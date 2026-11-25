FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.4 requests==2.32.3 boto3==1.35.90 redis==5.2.1
WORKDIR /tests
CMD ["pytest", "-v", "-p", "no:cacheprovider", "--junitxml=/report/e2e.xml", "."]
