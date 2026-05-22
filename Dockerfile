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

# v0.2.0 Cloud Run Web Surface (DISABLED skeleton — Card 10).
# The entrypoint module ``web_surface_entry.py`` is picked up by the
# ``COPY *.py /app/`` line above. When v0.2.0 activation lands (a
# future card), a split-deployment build would override CMD with:
#   CMD exec uvicorn web_surface_entry:create_web_surface_app \
#       --factory --host 0.0.0.0 --port ${PORT}
# Until then nothing changes: this single-stage build keeps running
# ``app:app`` and the surface module sits inert in the image.

COPY BUILD_VERSION /app/BUILD_VERSION
ENV BUILD_VERSION_FILE=/app/BUILD_VERSION

ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT}
