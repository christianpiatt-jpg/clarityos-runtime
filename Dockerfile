FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Runtime modules — explicit allowlist. When a new top-level package
# directory is added to the repo, add a COPY line here, or the
# container will hit ModuleNotFoundError at startup.
#   ELINS/          forecast/regional engine
#   el_ins/         v69 EL/INS analyzer + timeline
#   problem_solver/ v75+ ProblemSolver.REGRESSION_FIRST kernel
COPY *.py /app/
COPY ELINS/ /app/ELINS/
COPY el_ins/ /app/el_ins/
COPY problem_solver/ /app/problem_solver/

COPY BUILD_VERSION /app/BUILD_VERSION
ENV BUILD_VERSION_FILE=/app/BUILD_VERSION

ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT}
