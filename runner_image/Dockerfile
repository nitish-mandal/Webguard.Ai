# Trusted dependency preparation only. No target repository is in this context.
# Supply an operator-reviewed immutable Python 3.12 Linux base reference.
ARG PYTHON_BASE
FROM ${PYTHON_BASE}
ARG PROFILE_DIGEST
LABEL io.webguard.runner="1" io.webguard.python="3.12" io.webguard.profile="${PROFILE_DIGEST}"
COPY requirements.lock /opt/webguard/requirements.lock
COPY wheels/ /wheels/
RUN ["python", "-m", "pip", "install", "--no-cache-dir", "--no-index", "--find-links=/wheels", "--require-hashes", "--no-deps", "--only-binary=:all:", "-r", "/opt/webguard/requirements.lock"]
COPY entrypoint.py stage.py profile.json pytest.ini /opt/webguard/
COPY webguard_report.py /usr/local/lib/python3.12/site-packages/webguard_report.py
COPY check_policy.py /usr/local/lib/python3.12/site-packages/webguard_checks.py
COPY test_pagination_regression.py /opt/webguard/regressions/test_pagination.py
RUN ["python", "-I", "-c", "import pathlib,sys,pytest; assert sys.version_info[:2]==(3,12); assert pytest.__version__=='9.2.0'; [pathlib.Path(p).mkdir(exist_ok=True) for p in ('/scratch','/input')]; p=pathlib.Path('/opt/webguard/readonly-probe'); p.write_text('readonly probe'); p.chmod(0o666)"]
ENV PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
WORKDIR /scratch
USER 10001:10001
ENTRYPOINT ["python", "-I", "/opt/webguard/entrypoint.py"]
CMD []
