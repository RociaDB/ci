# Les dépendances sont résolues par architecture en amont par la CI
# (`uv pip install --python-platform`), l'image ne fait que les copier.
#
# CONTRAINTE MULTI-ARCH : aucune instruction RUN. C'est aussi pourquoi
# l'utilisateur est numérique — créer un compte demanderait un RUN.
FROM python:3.13-slim

ARG TARGETARCH
WORKDIR /app

COPY dist/${TARGETARCH}/site-packages /usr/local/lib/python3.13/site-packages
COPY src ./src

USER 1000:1000
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# Remplacer par le module d'entrée du projet.
ENTRYPOINT ["python", "-m", "rocia"]
